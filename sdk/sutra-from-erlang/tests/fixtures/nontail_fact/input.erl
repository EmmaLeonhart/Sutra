-module(nontail_fact).
-export([fac/1, main/0]).

fac(N) -> if N == 0 -> 1; true -> N * fac(N - 1) end.

main() -> fac(5).
