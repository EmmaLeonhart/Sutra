-module(tail_rec).
-export([sum_to/2, main/0]).

sum_to(Acc, N) -> if N == 0 -> Acc; true -> sum_to(Acc + N, N - 1) end.

main() -> sum_to(0, 5).
