-module(case_dispatch).
-export([pick/1, main/0]).

pick(X) -> case X of 1 -> 10; 2 -> 20; _ -> 99 end.

main() -> pick(2) + pick(7).
