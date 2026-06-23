"""Sutra → thrml (Extropic) compile target — ADDITIVE, experimental.

A SECOND, opt-in backend selected by `--emit-thrml` (queue.md approach G). It
lowers a validated Sutra subset to a thrml/JAX **energy-based-sampling** program:
values → spin registers, operations → factors, results recovered by sampling. The
canonical PyTorch backend (`codegen_pytorch.py`) and the `--emit`/`--run` path are
UNTOUCHED by this file — purely additive (non-destructive constraint, queue.md
§thrml).

The op→factor mappings are measured in `planning/open-questions/2026-06-13-sutra-
to-thrml-mapping.md` and the demos under `experiments/thrml/`.

Status: **G.0** entry point wired; **G.1/G.2** single-op bind compiles AND samples
(1.000); **G.3 (here)** generalizes to a small bind/unbind OP-GRAPH — multi-
statement `main` bodies with `vector tmp = bind/unbind(x, y);` intermediates and a
final `return …`. Each value is an N-bit spin register; bind and unbind are both
the 3-body product factor `arg1_i·arg2_i·out_i = +1` (so `unbind(bind(a,b),a)=b`);
atoms are clamped, intermediates+result are free and sampled jointly; the emitted
program self-verifies the sampled result against the host-computed ground truth.
Anything outside this subset raises `ThrmlCodegenNotSupported` (surface the gap,
never mislower).
"""
from __future__ import annotations

from . import ast_nodes as ast

_OPS = ("bind", "unbind")   # both = the element-wise product (3-body) factor


class ThrmlCodegenNotSupported(Exception):
    """Raised for any Sutra construct the thrml backend cannot yet lower. Carries
    a precise, user-facing reason; `__main__._emit_thrml` prints it as a
    `thrml-codegen:` diagnostic and exits non-zero (no silent mislowering)."""


def _basis_atoms(module) -> dict:
    """Top-level `vector NAME = embed("...");` declarations → {name: index}.

    `embed("...")` parses to an `EmbedExpr`; the legacy `basis_vector("...")` alias
    (deprecated 2026-06-23) parses to a `Call` — accept both so repointed programs
    keep their atom mapping.
    """
    atoms: dict = {}
    for item in module.items:
        if not (isinstance(item, ast.VarDecl) and item.initializer is not None):
            continue
        init = item.initializer
        is_embed = isinstance(init, ast.EmbedExpr)
        is_legacy = (isinstance(init, ast.Call)
                     and isinstance(init.callee, ast.Identifier)
                     and init.callee.name == "basis_vector")
        if is_embed or is_legacy:
            atoms[item.name] = len(atoms)
    return atoms


def _op_call(expr):
    """If `expr` is `bind(x, y)`/`unbind(x, y)` over two identifiers, return
    (op, x_name, y_name); else None."""
    if (isinstance(expr, ast.Call) and isinstance(expr.callee, ast.Identifier)
            and expr.callee.name in _OPS and len(expr.args) == 2
            and all(isinstance(a, ast.Identifier) for a in expr.args)):
        return expr.callee.name, expr.args[0].name, expr.args[1].name
    return None


def translate_thrml(module, *, dim: int = 16, seed: int = 0) -> str:
    """Lower a parsed Sutra `module` to a thrml/JAX program string (G.3 subset)."""
    atoms = _basis_atoms(module)
    main_fn = next((it for it in module.items
                    if isinstance(it, ast.FunctionDecl) and it.name == "main"), None)
    if main_fn is None:
        raise ThrmlCodegenNotSupported("no `main` function to lower")

    known = set(atoms)            # names with a definition (atoms + intermediates)
    steps: list = []              # (out_name, op, arg1, arg2) in evaluation order
    result_name = None
    for st in main_fn.body.statements:
        if isinstance(st, ast.VarDecl) and st.initializer is not None:
            call = _op_call(st.initializer)
            if call is None:
                raise ThrmlCodegenNotSupported(
                    "G.3 local `vector …` must be `bind`/`unbind` of two known "
                    "names (atoms or earlier intermediates)")
            op, a1, a2 = call
            for nm in (a1, a2):
                if nm not in known:
                    raise ThrmlCodegenNotSupported(f"{nm!r} is not defined before use")
            steps.append((st.name, op, a1, a2))
            known.add(st.name)
        elif isinstance(st, ast.ReturnStmt) and st.value is not None:
            val = st.value
            if isinstance(val, ast.Identifier):
                if val.name not in known:
                    raise ThrmlCodegenNotSupported(f"return of unknown {val.name!r}")
                result_name = val.name
            else:
                call = _op_call(val)
                if call is None:
                    raise ThrmlCodegenNotSupported(
                        "G.3 `return` must be a name or a bind/unbind of two names")
                op, a1, a2 = call
                for nm in (a1, a2):
                    if nm not in known:
                        raise ThrmlCodegenNotSupported(f"{nm!r} is not defined before use")
                steps.append(("_result", op, a1, a2))
                known.add("_result")
                result_name = "_result"
            break
        else:
            raise ThrmlCodegenNotSupported(
                f"G.3 supports only `vector x = bind/unbind(...)` + `return …`; "
                f"got {type(st).__name__}")
    if result_name is None:
        raise ThrmlCodegenNotSupported("`main` has no return")
    if result_name in atoms and not steps:
        raise ThrmlCodegenNotSupported("returning a bare atom is a no-op (nothing to sample)")
    return _emit_graph(list(atoms), steps, result_name, dim, seed)


def _emit_graph(atom_names, steps, result_name, dim, seed) -> str:
    """Emit a self-verifying thrml program for a bind/unbind op-graph. Atoms are
    clamped N-bit spin registers; every intermediate/result is free and pinned by
    a 3-body product factor over its two inputs; all are sampled jointly. Ground
    truth follows the same element-wise-product graph on the host."""
    return f'''"""Generated by sutra-from-thrml codegen (approach G.3). Lowers a
bind/unbind op-graph to an energy-based thrml program: values = {dim}-bit spin
registers, each bind/unbind = the 3-body product factor in1_i*in2_i*out_i = +1,
results by joint block-Gibbs sampling. Self-verifies against the host-computed
ground truth."""
import jax
import jax.numpy as jnp
from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.block_sampling import BlockGibbsSpec
from thrml.factor import FactorSamplingProgram
from thrml.models import SpinEBMFactor, SpinGibbsConditional

_N = {dim}
_SD = {{SpinNode: jax.ShapeDtypeStruct((), jnp.bool_)}}
_BETA = 6.0
_key = jax.random.key({seed})

_atoms = {atom_names!r}
_steps = {steps!r}                # (out, op, in1, in2)
_result = {result_name!r}

# Compile-time register per atom + host ground truth following the op-graph.
_reg = {{}}
for _i, _nm in enumerate(_atoms):
    _reg[_nm] = 2 * jax.random.bernoulli(
        jax.random.fold_in(_key, _i), 0.5, (_N,)).astype(jnp.int32) - 1
for _out, _op, _a, _b in _steps:
    _reg[_out] = _reg[_a] * _reg[_b]   # bind/unbind = element-wise product

# Spin nodes for every value; atoms clamped, intermediates+result free.
_nodes = {{nm: [SpinNode() for _ in range(_N)] for nm in list(_atoms) + [s[0] for s in _steps]}}
_factors = [SpinEBMFactor([Block(_nodes[a]), Block(_nodes[b]), Block(_nodes[out])],
                          _BETA * jnp.ones((_N,))) for (out, _op, a, b) in _steps]
_free_names = [s[0] for s in _steps]
_free_nodes = [n for nm in _free_names for n in _nodes[nm]]
_clamp_nodes = [n for nm in _atoms for n in _nodes[nm]]
_spec = BlockGibbsSpec([Block([n]) for n in _free_nodes], [Block(_clamp_nodes)], _SD)
_prog = FactorSamplingProgram(_spec, [SpinGibbsConditional() for _ in _free_nodes],
                              _factors, [])
_clamp = jnp.concatenate([(_reg[nm] == 1) for nm in _atoms]).astype(bool)
_init = [jax.random.bernoulli(jax.random.fold_in(_key, 1000 + _i), 0.5, (1,))
         for _i in range(len(_free_nodes))]
_sched = SamplingSchedule(n_warmup=120, n_samples=160, steps_per_sample=3)
_obs = sample_states(jax.random.key({seed} + 1), _prog, _sched, _init, [_clamp],
                     [Block(_nodes[_result])])
_u = (jnp.mean(jnp.asarray(_obs[0]).astype(jnp.float32), axis=0) > 0.5)
_u_pm1 = 2 * _u.astype(jnp.int32) - 1
_truth = _reg[_result]
_acc = float(jnp.mean((_u_pm1 == _truth).astype(jnp.float32)))
print(f"thrml op-graph -> {{_result}}: sampled vs ground-truth per-bit = {{_acc:.3f}} "
      f"(N={{_N}}, {{len(_steps)}} op(s))")
'''
