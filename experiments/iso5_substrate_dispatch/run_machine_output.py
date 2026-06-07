import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
su=open("experiments/iso5_substrate_dispatch/mini_wasm_machine.su").read()
lx=Lexer(su,file="<t>");ast=Parser(lx.tokenize(),file="<t>",diagnostics=lx.diagnostics).parse_module()
assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
ns={};exec(translate_module(ast,llm_model="none",runtime_dim=2),ns);v=ns["_VSA"]
def run(prog, steps, read):
    ram=[v.zero_vector() for _ in range(512)]
    ram[0]=v.make_real(10.0); ram[1]=v.make_real(0.0); ram[2]=v.make_real(0.0); ram[3]=v.make_real(0.0)
    for k,(o,i) in enumerate(prog): ram[10+2*k]=v.make_real(float(o)); ram[11+2*k]=v.make_real(float(i))
    v.ram=ram
    for _ in range(steps): ns["step"](0.0)
    return [round(float(v.real(ram[a]))) for a in read]
# 11=OUTPUT. emit 72,73,74 ("HIJ") -> buffer at 300,301,302
out = run([(1,72),(11,0),(1,73),(11,0),(1,74),(11,0),(0,0)], 12, [300,301,302])
print("output buffer [300..302] =", out, "(expect [72,73,74])")
print("as chars:", "".join(chr(c) for c in out))
# regression
r = run([(1,3),(1,4),(2,0),(0,0)], 8, [100]); print("3+4 ->", r[0], "(7)")
