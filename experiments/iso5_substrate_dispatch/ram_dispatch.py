import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
def compile_src(src, dim=2):
    lx=Lexer(src,file="<t>"); toks=lx.tokenize()
    ast=Parser(toks,file="<t>",diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns={}; exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns); return ns
# recurring-cursor step (NTM-read-head idiom): each call reads opcode at cur, dispatches
# vs literal 99, advances cur. Mirrors test_synchronous_ram_read_in_recur.
src=('function vector step(scalar dummy) {'
     '  recurring vector cur = make_real(0.0);'
     '  int op = ramRead(cur).real();'
     '  recur(cur + make_real(1.0));'
     '  return make_real(truth_axis(defuzzy(op == 99))); }'
     'function string main() { return "ok"; }')
ns=compile_src(src); v=ns["_VSA"]
v.ram=[v.make_real(10.0), v.make_real(20.0), v.make_real(99.0)]+[v.zero_vector() for _ in range(5)]
out=[round(float(v.real(ns["step"](0.0))),3) for _ in range(3)]
print("recur dispatch truth(op==99) per step [expect -1,-1,+1] =", out)

# MEASURED 2026-06-06: prints [-1.0, -1.0, 1.0] — fresh ramRead(cur).real() == 99
# dispatches cleanly in the recurring-cursor (autoregressive step) form. See
# planning/findings/2026-06-06-iso5-ram-based-machine-dispatch-works.md
