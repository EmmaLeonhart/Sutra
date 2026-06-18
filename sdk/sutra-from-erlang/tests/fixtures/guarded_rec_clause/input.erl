-module(guarded_rec_clause).
-export([main/0]).

f(N, Acc) when N > 0 -> f(N - 1, Acc + N);
f(_, Acc) -> Acc.

main() -> f(5, 0).
