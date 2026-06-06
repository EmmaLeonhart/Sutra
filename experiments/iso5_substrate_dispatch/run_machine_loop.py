import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
su=open("experiments/iso5_substrate_dispatch/mini_wasm_machine.su").read()
lx=Lexer(su,file="<t>");ast=Parser(lx.tokenize(),file="<t>",diagnostics=lx.diagnostics).parse_module()
ns={};exec(translate_module(ast,llm_model="none",runtime_dim=2),ns);v=ns["_VSA"]
def run(prog, steps, addr):
    ram=[v.zero_vector() for _ in range(512)]
    ram[0]=v.make_real(10.0); ram[1]=v.make_real(0.0); ram[2]=v.make_real(0.0)
    for k,(o,i) in enumerate(prog): ram[10+2*k]=v.make_real(float(o)); ram[11+2*k]=v.make_real(float(i))
    v.ram=ram
    for _ in range(steps): ns["step"](0.0)
    return round(float(v.real(ram[addr])))
# Loop: counter@200=N, acc@201=0; each iter acc++, counter--, br_if back to LOOP(22).
def loop_prog(N): return [
 (1,200),(1,N),(8,0),        # ram[200]=N
 (1,201),(1,0),(8,0),        # ram[201]=0
 # LOOP @ addr 22:
 (1,201),(1,201),(7,0),(1,1),(2,0),(8,0),   # ram[201] = acc + 1
 (1,200),(1,200),(7,0),(1,1),(3,0),(8,0),   # ram[200] = counter - 1
 (1,200),(7,0),(6,22),       # if counter-1 != 0, jump to LOOP(22)
 (0,0),                       # halt
]
for N in (1,3,5):
    print(f"countdown loop N={N}: acc@201 =", run(loop_prog(N), 200, 201), f"(expect {N})")
