import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
su=open("experiments/iso5_substrate_dispatch/mini_wasm_machine.su").read()
lx=Lexer(su,file="<t>");ast=Parser(lx.tokenize(),file="<t>",diagnostics=lx.diagnostics).parse_module()
ns={};exec(translate_module(ast,llm_model="none",runtime_dim=2),ns);v=ns["_VSA"]
def run(prog, steps=8):
    ram=[v.zero_vector() for _ in range(256)]
    ram[0]=v.make_real(10.0); ram[1]=v.make_real(0.0); ram[2]=v.make_real(0.0)
    for k,(o,i) in enumerate(prog): ram[10+2*k]=v.make_real(float(o)); ram[11+2*k]=v.make_real(float(i))
    v.ram=ram
    for _ in range(steps): ns["step"](0.0)
    return round(float(v.real(ram[100])))
# program-as-data: same machine, different programs
print("const 5; const 6; add  -> ", run([(1,5),(1,6),(2,0),(0,0)]), "(expect 11)")
print("const 9; const 9; add  -> ", run([(1,9),(1,9),(2,0),(0,0)]), "(expect 18)")
print("const 100;const 23;add -> ", run([(1,100),(1,23),(2,0),(0,0)]), "(expect 123)")
# chained: const 1; const 2; add; const 3; add -> 6  (needs deeper run)
print("1+2 then +3            -> ", run([(1,1),(1,2),(2,0),(1,3),(2,0),(0,0)],steps=10), "(expect 6)")
