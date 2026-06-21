-module(multiarg_nontail_multibase).
-export([f/2, main/0]).

f(0, B) -> B;
f(1, B) -> B + 100;
f(A, B) -> A + f(A - 1, B).

main() -> f(3, 10).
