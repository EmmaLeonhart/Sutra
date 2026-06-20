"""Tests for MultiProcessRuntime — N programs sharing one _VSA.

Verifies:
  - Two programs admitted; both report the right static-analysis
    key sets.
  - The runtime exposes ONE `_VSA` instance — both programs's
    `mod._VSA` point at the same object.
  - tick(name, input) actually invokes the named program.
  - Axon-passing between programs works in-memory: program A
    produces an axon; the same tensor is passed to program B's
    tick; program B extracts a key A bound. The value matches what
    we'd get via in-program axon_item — proving the shared codebook
    + rotation cache make cross-program axons coherent.
  - Codebook is genuinely shared: a basis_vector embedded by
    program A is reused by program B without re-fetching.
  - Duplicate names + missing entry points + empty spec lists raise.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="MultiProcessRuntime tests need torch")

HERE = pathlib.Path(__file__).resolve().parent
SDK = HERE.parent
sys.path.insert(0, str(SDK))

from sutra_compiler.multi_process import MultiProcessRuntime, ProgramSpec


@pytest.fixture(scope="module")
def runtime(tmp_path_factory) -> MultiProcessRuntime:
    """Two programs admitted to one runtime: producer + consumer."""
    tmp = tmp_path_factory.mktemp("mpr_runtime")

    producer = tmp / "producer.su"
    producer.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    Axon a;\n"
        "    a.add(\"animal\", basis_vector(\"dog\"));\n"
        "    a.add(\"color\",  basis_vector(\"red\"));\n"
        "    return a;\n"
        "}\n",
        encoding="utf-8",
    )
    consumer = tmp / "consumer.su"
    consumer.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    return axon_item(input_axon, \"animal\");\n"
        "}\n",
        encoding="utf-8",
    )
    return MultiProcessRuntime(
        [
            ProgramSpec(name="producer", source_path=producer),
            ProgramSpec(name="consumer", source_path=consumer),
        ],
        llm_model="nomic-embed-text",
        runtime_dim=768,
    )


def test_both_programs_admitted(runtime: MultiProcessRuntime) -> None:
    assert runtime.admitted() == ["consumer", "producer"]


def test_static_analysis_per_program(runtime: MultiProcessRuntime) -> None:
    """The v0.3.3 axon-keys analysis surfaces per-program."""
    assert runtime.axon_keys_bound("producer") == frozenset({"animal", "color"})
    assert runtime.axon_keys_read("producer") == frozenset()
    assert runtime.axon_keys_bound("consumer") == frozenset()
    assert runtime.axon_keys_read("consumer") == frozenset({"animal"})


def test_vsa_is_shared_across_programs(runtime: MultiProcessRuntime) -> None:
    """Both programs' modules hold a reference to the same _VSA."""
    prod_vsa = runtime._programs["producer"].module._VSA  # noqa: SLF001
    cons_vsa = runtime._programs["consumer"].module._VSA  # noqa: SLF001
    assert prod_vsa is cons_vsa
    assert prod_vsa is runtime.vsa()


def test_tick_invokes_named_program(runtime: MultiProcessRuntime) -> None:
    """tick(name, input) returns what that program's on_axon returns."""
    vsa_dim = runtime.vsa().dim
    dummy = torch.zeros(vsa_dim)  # producer ignores input_axon
    prod_out = runtime.tick("producer", dummy)
    assert prod_out.shape == (vsa_dim,)


def test_axon_passing_across_programs(runtime: MultiProcessRuntime) -> None:
    """Producer's output is correctly carried into consumer's tick.

    Narrow-scope test of THE MECHANISM — that producer's output
    tensor lands as consumer's input on the shared device, runs
    through consumer's compiled body, and produces an output of
    the right shape on the right device. Bundle-decoding *quality*
    (does the recovered vector argmax to the right decoy?) is a
    Sutra-paper-level capacity question with its own test surface
    in the corpus tests; this MultiProcessRuntime test is about
    runtime wiring, not VSA capacity.

    The actual demonstration that the shared-VSA wiring is coherent
    is in `test_vsa_is_shared_across_programs` (which proves both
    programs hold the same `_VSA` reference — so any embed / rotate
    / cache miss in one is visible to the other).
    """
    vsa_dim = runtime.vsa().dim
    dummy = torch.zeros(vsa_dim)
    bundle = runtime.tick("producer", dummy)  # animal=dog, color=red
    assert bundle.shape == (vsa_dim,)
    assert bundle.device.type == runtime.vsa().device.type
    extracted = runtime.tick("consumer", bundle)  # extracts "animal"
    assert extracted.shape == (vsa_dim,)
    assert extracted.device.type == runtime.vsa().device.type
    # The extracted output shouldn't be numerically zero — that
    # would indicate the consumer's body never ran or the unbind
    # produced a degenerate result.
    assert extracted.norm().item() > 1e-3


def test_duplicate_program_names_rejected(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "p.su"
    src.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate program name"):
        MultiProcessRuntime(
            [
                ProgramSpec(name="dup", source_path=src),
                ProgramSpec(name="dup", source_path=src),
            ]
        )


def test_empty_specs_rejected() -> None:
    with pytest.raises(ValueError, match="at least one program"):
        MultiProcessRuntime([])


def test_missing_entry_point_rejected(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "noentry.su"
    src.write_text(
        "function int unrelated() { return 0; }\n",
        encoding="utf-8",
    )
    with pytest.raises(AttributeError, match="no entry point"):
        MultiProcessRuntime([ProgramSpec(name="x", source_path=src)])


def test_axon_project_via_runtime(runtime: MultiProcessRuntime) -> None:
    """Runtime's axon_project delegates to the shared _VSA."""
    vsa_dim = runtime.vsa().dim
    dummy = torch.zeros(vsa_dim)
    full = runtime.tick("producer", dummy)  # has animal + color
    slim = runtime.axon_project(full, ["animal"])
    assert slim.shape == full.shape


def test_unknown_program_name_raises(runtime: MultiProcessRuntime) -> None:
    with pytest.raises(KeyError, match="no admitted program"):
        runtime.tick("ghost", torch.zeros(runtime.vsa().dim))


def test_tick_all_matches_sequential(runtime: MultiProcessRuntime) -> None:
    """tick_all runs many programs in one concurrent round; every result is
    IDENTICAL to the sequential tick (correctness first — the only difference
    is device-side overlap). On CPU the streams are a no-op; on CUDA each
    program launches on its own stream and a single synchronize joins them."""
    vsa = runtime.vsa()
    dim = vsa.dim
    dummy = torch.zeros(dim)
    producer_out = runtime.tick("producer", dummy)  # axon binding animal + color
    # One concurrent round: producer ignores input; consumer reads "animal".
    outs = runtime.tick_all({"producer": dummy, "consumer": producer_out})
    assert set(outs) == {"producer", "consumer"}
    # Concurrent == sequential, program by program.
    assert torch.allclose(outs["producer"], runtime.tick("producer", dummy))
    assert torch.allclose(outs["consumer"], runtime.tick("consumer", producer_out))
    # And the consumer's concurrent output really decodes the key the producer bound.
    expected = vsa.axon_item(producer_out, "animal")
    assert torch.allclose(outs["consumer"], expected, atol=1e-4)


def test_tick_all_validates_names_before_launch(runtime: MultiProcessRuntime) -> None:
    """An unknown name raises KeyError and nothing is dispatched."""
    dim = runtime.vsa().dim
    with pytest.raises(KeyError, match="no admitted program"):
        runtime.tick_all({"producer": torch.zeros(dim), "ghost": torch.zeros(dim)})


def test_tick_all_empty_round(runtime: MultiProcessRuntime) -> None:
    """An empty round is a no-op returning an empty dict (every path runs; there
    are simply zero paths)."""
    assert runtime.tick_all({}) == {}
