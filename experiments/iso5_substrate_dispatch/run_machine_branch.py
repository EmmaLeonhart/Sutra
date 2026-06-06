import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
su=open("experiments/iso5_substrate_dispatch/mini_wasm_machine.su").read()
lx=Lexer(su,file="<t>");ast=Parser(lx.tokenize(),file="<t>",diagnostics=lx.diagnostics).parse_module()
assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
ns={};exec(translate_module(ast,llm_model="none",runtime_dim=2),ns);v=ns["_VSA"]
def run(prog, steps=10):
    ram=[v.zero_vector() for _ in range(256)]
    ram[0]=v.make_real(10.0); ram[1]=v.make_real(0.0); ram[2]=v.make_real(0.0)
    for k,(o,i) in enumerate(prog): ram[10+2*k]=v.make_real(float(o)); ram[11+2*k]=v.make_real(float(i))
    v.ram=ram
    for _ in range(steps): ns["step"](0.0)
    return round(float(v.real(ram[100])))
# 6=BR_IF imm=absolute target. prog: const cond; br_if 18; const 100; halt; const 7; halt
def cond_prog(c): return [(1,c),(6,18),(1,100),(0,0),(1,7),(0,0)]
print("cond=1 (branch TAKEN -> 7)     ->", run(cond_prog(1)), "(7)")
print("cond=0 (NOT taken -> 100)      ->", run(cond_prog(0)), "(100)")
# regression: arithmetic still works
print("const 3; const 4; add          ->", run([(1,3),(1,4),(2,0),(0,0)]), "(7)")
print("const 12; const 10; AND        ->", run([(1,12),(1,10),(5,0),(0,0)]), "(8)")
