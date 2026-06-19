-module(guarded_multibase).
-export([f/2, main/0]).

f(0, Acc) -> Acc;
f(1, Acc) -> Acc + 100;
f(N, Acc) when N > 50 -> Acc + 9000;
f(N, Acc) -> f(N - 1, Acc + N).

main() -> f(5, 0) + f(60, 0).
