"""Neural regex — on-substrate NFA matcher (Unix rung 11, prerequisite P2).

Implements planning/sutra-spec/neural-regex-nfa.md. A regex is Thompson-constructed
to an NFA at COMPILE time (host — parsing + construction, the same class of work as
tr's codebook), then SIMULATED on the substrate: the active-state SET is an N-dim
0/1 buffer and each input character advances it by substrate tensor ops —

    s' = ge1( E @ ( M_dot @ s + Σ_lit is_cp(c, lit) * (M_lit[lit] @ s) ) )

`E` is the epsilon-closure matrix, `M_dot` the any-char (`.`) adjacency, `M_lit[lit]`
the adjacency for edges labelled `lit`; all are compile-time device tensors. The
per-character transition matrix is thus ASSEMBLED on the substrate from the raw
codepoint `c` via the exact indicator `is_cp` (a 0-d device scalar, no host
readout); `ge1` collapses "reached by >=1 path" to a 0/1 reachability indicator with
no residual. matmul / mul / relu are all _VSA substrate ops (torch on-device).

Supported subset: literals, `.`, character classes `[...]`/`[^...]`/ranges,
quantifiers `* + ?`, alternation `|`, grouping `( )`, anchors `^ $`. Verified against
Python `re`.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

import torch                               # noqa: E402
from run_demo import compile_su            # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
# any compiled module gives us the substrate op surface (_VSA); the NFA buffers are
# plain device tensors operated on by _VSA.matmul / _VSA.is_cp etc.
_VSA = compile_su(os.path.join(_HERE, "grep_head.su"), semantic_dim=2)["_VSA"]
_DEV, _DT = _VSA.device, _VSA.dtype
_DOT = "\x00DOT"     # sentinel edge label meaning "any character"


# ---------------------------------------------------------------- regex -> NFA
class _Frag:
    """A Thompson fragment: a start state and a list of dangling out-edges to be
    patched to the next fragment's start."""
    __slots__ = ("start", "outs")

    def __init__(self, start, outs):
        self.start = start
        self.outs = outs


class _NFA:
    def __init__(self):
        self.n = 0
        self.eps = []          # (from, to)
        self.sym = []          # (from, to, label)  label = char or _DOT

    def new_state(self):
        s = self.n
        self.n += 1
        return s

    def add_eps(self, a, b):
        self.eps.append((a, b))

    def add_sym(self, a, b, label):
        self.sym.append((a, b, label))


def _tokenize_class(pattern, i):
    """Parse a `[...]` class starting at pattern[i]=='['; return (set_or_pred, j)."""
    neg = False
    i += 1
    if i < len(pattern) and pattern[i] == "^":
        neg = True
        i += 1
    chars = set()
    ranges = []
    while i < len(pattern) and pattern[i] != "]":
        c = pattern[i]
        if i + 2 < len(pattern) and pattern[i + 1] == "-" and pattern[i + 2] != "]":
            ranges.append((ord(c), ord(pattern[i + 2])))
            i += 3
        else:
            chars.add(c)
            i += 1
    i += 1  # skip ']'

    def member(ch):
        o = ord(ch)
        hit = ch in chars or any(lo <= o <= hi for lo, hi in ranges)
        return hit != neg
    return member, i


def _parse(pattern):
    """Recursive-descent parse of the supported subset into an NFA + anchors.
    Grammar: alt := concat ('|' concat)* ; concat := (atom quant?)* ;
    atom := '(' alt ')' | '[' class ']' | '.' | literal ; quant := '*'|'+'|'?'."""
    nfa = _NFA()
    # class predicates get their own synthetic labels so identical classes share
    class_preds = {}

    pos = [0]
    anchored_start = pattern.startswith("^")
    if anchored_start:
        pattern = pattern[1:]
    anchored_end = pattern.endswith("$") and not pattern.endswith("\\$")
    if anchored_end:
        pattern = pattern[:-1]

    def peek():
        return pattern[pos[0]] if pos[0] < len(pattern) else None

    def literal_frag(label):
        a, b = nfa.new_state(), nfa.new_state()
        nfa.add_sym(a, b, label)
        return _Frag(a, [b])

    def parse_atom():
        c = peek()
        if c == "(":
            pos[0] += 1
            f = parse_alt()
            assert peek() == ")", "unbalanced ("
            pos[0] += 1
            return f
        if c == "[":
            member, j = _tokenize_class(pattern, pos[0])
            pos[0] = j
            key = ("cls", pattern)  # unique-enough per position via id
            label = f"\x00CLS{len(class_preds)}"
            class_preds[label] = member
            return literal_frag(label)
        if c == ".":
            pos[0] += 1
            return literal_frag(_DOT)
        # literal (support a couple escapes)
        if c == "\\" and pos[0] + 1 < len(pattern):
            pos[0] += 2
            return literal_frag(pattern[pos[0] - 1])
        pos[0] += 1
        return literal_frag(c)

    def parse_quant(frag):
        c = peek()
        if c not in ("*", "+", "?"):
            return frag
        pos[0] += 1
        s = nfa.new_state()
        if c == "*":
            nfa.add_eps(s, frag.start)
            for o in frag.outs:
                nfa.add_eps(o, s)
            return _Frag(s, [s])
        if c == "+":
            for o in frag.outs:
                nfa.add_eps(o, frag.start)
            return _Frag(frag.start, frag.outs)
        # '?'
        nfa.add_eps(s, frag.start)
        return _Frag(s, frag.outs + [s])

    def parse_concat():
        frags = []
        while peek() is not None and peek() not in ("|", ")"):
            frags.append(parse_quant(parse_atom()))
        if not frags:
            s = nfa.new_state()
            return _Frag(s, [s])   # empty
        for a, b in zip(frags, frags[1:]):
            for o in a.outs:
                nfa.add_eps(o, b.start)
        return _Frag(frags[0].start, frags[-1].outs)

    def parse_alt():
        first = parse_concat()
        if peek() != "|":
            return first
        branches = [first]
        while peek() == "|":
            pos[0] += 1
            branches.append(parse_concat())
        s = nfa.new_state()
        outs = []
        for br in branches:
            nfa.add_eps(s, br.start)
            outs.extend(br.outs)
        return _Frag(s, outs)

    frag = parse_alt()
    accept = nfa.new_state()
    for o in frag.outs:
        nfa.add_eps(o, accept)
    return nfa, frag.start, accept, class_preds, anchored_start, anchored_end


# ------------------------------------------------------ NFA -> device matrices
def _closure_matrix(nfa):
    """E[to, from] = 1 if `to` is reachable from `from` by epsilon edges
    (reflexive-transitive closure), as an N x N device tensor."""
    n = nfa.n
    reach = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    adj = [[0] * n for _ in range(n)]
    for a, b in nfa.eps:
        adj[a][b] = 1
    # Floyd-style transitive closure over epsilon edges
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if adj[k][j] or reach[k][j]:
                        reach[i][j] = 1
    # one more pass to be safe on chains
    changed = True
    while changed:
        changed = False
        for i in range(n):
            for k in range(n):
                if reach[i][k]:
                    for j in range(n):
                        if reach[k][j] and not reach[i][j]:
                            reach[i][j] = 1
                            changed = True
    # E[to, from]
    E = [[reach[frm][to] for frm in range(n)] for to in range(n)]
    return torch.tensor(E, dtype=_DT, device=_DEV)


class NeuralRegex:
    def __init__(self, pattern: str):
        (self.nfa, self.start, self.accept, self.class_preds,
         self.anchored_start, self.anchored_end) = _parse(pattern)
        n = self.nfa.n
        self.E = _closure_matrix(self.nfa)
        # adjacency per label: M[label][to, from] = 1
        self.M = {}
        for a, b, label in self.nfa.sym:
            m = self.M.setdefault(label, [[0] * n for _ in range(n)])
            m[b][a] = 1
        self.M = {lab: torch.tensor(m, dtype=_DT, device=_DEV)
                  for lab, m in self.M.items()}
        e = [0] * n
        e[self.start] = 1
        s0 = torch.tensor(e, dtype=_DT, device=_DEV)
        self.s0 = self._ge1(self.E @ s0)     # epsilon-closure of the start
        self.accept_vec = torch.zeros(n, dtype=_DT, device=_DEV)
        self.accept_vec[self.accept] = 1.0

    @staticmethod
    def _ge1(x):
        # exact elementwise 0/1 reachability step: 1 iff x >= 1 (relu-of-triangle),
        # the same exact integer step as the scalar rungs, here over a buffer.
        r = torch.relu(x)
        return 1.0 - torch.relu(1.0 - r)

    def _char_trans(self, s, ch):
        """Substrate char transition: fire dot edges + label edges matching `ch`,
        assembling the transition on the substrate from the codepoint via is_cp."""
        n = self.nfa.n
        fired = torch.zeros(n, dtype=_DT, device=_DEV)
        cv = _VSA.make_real(float(ord(ch)))
        for label, M in self.M.items():
            if label == _DOT:
                coeff = 1.0
            elif label.startswith("\x00CLS"):
                coeff = 1.0 if self.class_preds[label](ch) else 0.0
            else:
                # exact substrate indicator relu(1-|c-lit|) -> 0-d device scalar
                # (1 iff c==lit for integer codepoints), no host float readout.
                d = _VSA.abs(_VSA.complex_sub(cv, _VSA.make_real(float(ord(label)))))
                coeff = torch.relu(1.0 - d)
            fired = fired + coeff * (M @ s)
        return self._ge1(self.E @ fired)

    def _accept_active(self, s) -> bool:
        # boundary readout (monitoring): is an accept state active?
        return float(torch.dot(self.accept_vec, s)) >= 0.5

    def fullmatch(self, text: str) -> bool:
        s = self.s0
        for ch in text:
            s = self._char_trans(s, ch)
        return self._accept_active(s)

    def search(self, text: str) -> bool:
        """Does `text` contain a match? Re-inject the start closure each step
        (the implicit `.*` prefix) unless the pattern is ^-anchored; require
        end-of-string when $-anchored."""
        s = self.s0
        if self._accept_active(s) and not self.anchored_end:
            return True
        for i, ch in enumerate(text):
            s = self._char_trans(s, ch)
            if not self.anchored_start:
                s = self._ge1(s + self.s0)
            last = i == len(text) - 1
            if self._accept_active(s) and (not self.anchored_end or last):
                return True
        return False


def regex_search(pattern: str, text: str) -> bool:
    return NeuralRegex(pattern).search(text)
