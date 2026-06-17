"""Y1 — the stdin/stdout button substrate-server protocol (no subprocess).

`ButtonSubstrateServer` is the Yantra-spawnable bridge: a host painter (Yantra's Rust GUI /
orchestrator surface) sends one-line text commands and reads substrate-rendered button frames
+ state, mirroring `counter_substrate_server.py`. The substrate render and the owner+CTR
steering are the Sutra side; the host does window/clicks/paint. These tests drive the command
handler directly (no pipes) so CI can verify the protocol.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent
_SIZE = 16
_BODY_BYTES = _SIZE * _SIZE * 3 * 8        # float64 RGB frame


def _server(**kw):
    spec = importlib.util.spec_from_file_location("gui_button_substrate_server",
                                                  _DIR / "button_substrate_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ButtonSubstrateServer(size=_SIZE, seed=0, **kw)


def _split_frame(resp: bytes):
    head, body = resp.split(b"\n", 1)
    return head.decode(), body


def test_init_command_returns_a_frame():
    pytest.importorskip("torch")
    srv = _server()
    head, body = _split_frame(srv.handle("I"))
    parts = head.split()
    assert parts[0] == "FRAME" and int(parts[2]) == _SIZE, f"bad header: {head}"
    assert len(body) == _BODY_BYTES, f"frame body {len(body)} != {_BODY_BYTES}"


def test_variant_command_returns_a_frame():
    pytest.importorskip("torch")
    srv = _server()
    head, body = _split_frame(srv.handle("V"))
    assert head.split()[0] == "FRAME"
    assert len(body) == _BODY_BYTES


def test_owner_prefer_advances_round():
    pytest.importorskip("torch")
    srv = _server()
    assert srv.bridge.round == 0
    resp = srv.handle("PB")              # owner prefers the variant (B)
    assert resp.startswith(b"OK"), resp
    assert srv.bridge.round == 1, "owner-prefer did not advance the round"


def test_click_is_tallied():
    pytest.importorskip("torch")
    srv = _server()
    c0 = srv.bridge.clicks
    resp = srv.handle("CB")              # visitor clicks the variant
    assert resp == b"OK\n", resp
    assert srv.bridge.clicks == c0 + 1
    with pytest.raises(ValueError):
        srv.handle("CX")                # bad click target


def test_state_command_is_json_with_expected_keys():
    pytest.importorskip("torch")
    srv = _server()
    resp = srv.handle("S")
    assert resp.startswith(b"STATE ") and resp.endswith(b"\n")
    state = json.loads(resp[len(b"STATE "):].decode())
    for k in ("round", "clicks", "impressions", "ctr_observed", "copy", "theta"):
        assert k in state, f"state missing {k}: {state}"
    assert isinstance(state["theta"], dict) and "fr" in state["theta"]


def test_quit_returns_none():
    pytest.importorskip("torch")
    srv = _server()
    assert srv.handle("Q") is None
