import sys, pathlib
sys.path.insert(0, str(pathlib.Path("sdk/sutra-from-ocaml")))
sys.path.insert(0, str(pathlib.Path("sdk/sutra-compiler")))
from sutra_from_ocaml.lower import lower
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
ml="let f i v =\n  let a = Array.make 8 0 in\n  a.(i) <- v;\n  a.(i)\n"
su=lower(ml)
lx=Lexer(su,file="<t>"); toks=lx.tokenize()
ast=Parser(toks,file="<t>",diagnostics=lx.diagnostics).parse_module()
assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
ns={}; exec(translate_module(ast, llm_model="none", runtime_dim=2), ns); v=ns["_VSA"]
v.ram=[v.zero_vector() for _ in range(16)]
out=float(ns["f"](v.make_real(2.0), v.make_real(77.0)))
print("f(2,77) [write 77 at idx, read back; expect 77] =", round(out,3))
print("ram[2] =", round(float(v.real(v.ram[2])),3), "(expect 77)")
# multi-array base offsets
ml2="let g () =\n  let a = Array.make 4 0 in\n  let b = Array.make 4 0 in\n  a.(1) <- 11;\n  b.(1) <- 22;\n  a.(1) + b.(1)\n"
su2=lower(ml2); 
lx2=Lexer(su2,file="<t>"); ast2=Parser(lx2.tokenize(),file="<t>",diagnostics=lx2.diagnostics).parse_module()
ns2={}; exec(translate_module(ast2, llm_model="none", runtime_dim=2), ns2); v2=ns2["_VSA"]
v2.ram=[v2.zero_vector() for _ in range(8192)]
print("g() [a and b distinct RAM regions; 11+22; expect 33] =", round(float(ns2["g"]()),3))
print("--- g .su ---"); print(su2)
