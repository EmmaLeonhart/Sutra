-module(tuple_axon).
-export([main/0]).

fst(P) -> element(1, P) + element(2, P).

main() -> fst({5, 8}).
