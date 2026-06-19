-module(multibase_nontail_fact).
-export([f/1, main/0]).

f(0) -> 1;
f(1) -> 5;
f(N) -> N * f(N - 1).

main() -> f(5).
