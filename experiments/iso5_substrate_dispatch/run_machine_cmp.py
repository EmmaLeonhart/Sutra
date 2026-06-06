import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
su=open("experiments/iso5_substrate_dispatch/mini_wasm_machine.su").read()
lx=Lexer(su,file="<t>");ast=Parser(lx.tokenize(),file="<t>",diagnostics=lx.diagnostics).parse_module()
assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
ns={};exec(translate_module(ast,llm_model="none",runtime_dim=2),ns);v=ns["_VSA"]
def run(prog, steps=12, addr=100):
    ram=[v.zero_vector() for _ in range(512)]
    ram[0]=v.make_real(10.0); ram[1]=v.make_real(0.0); ram[2]=v.make_real(0.0)
    for k,(o,i) in enumerate(prog): ram[10+2*k]=v.make_real(float(o)); ram[11+2*k]=v.make_real(float(i))
    v.ram=ram
    for _ in range(steps): ns["step"](0.0)
    return round(float(v.real(ram[addr])))
# 9=EQ 10=LT.  top2 OP top1
print("3 < 5 ->", run([(1,3),(1,5),(10,0),(0,0)]), "(1)")
print("5 < 3 ->", run([(1,5),(1,3),(10,0),(0,0)]), "(0)")
print("7 == 7 ->", run([(1,7),(1,7),(9,0),(0,0)]), "(1)")
print("7 == 8 ->", run([(1,7),(1,8),(9,0),(0,0)]), "(0)")
# regression
print("3+4 ->", run([(1,3),(1,4),(2,0),(0,0)]), "(7)")
print("12&10 ->", run([(1,12),(1,10),(5,0),(0,0)]), "(8)")
