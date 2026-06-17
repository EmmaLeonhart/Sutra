sum(0, Acc) -> Acc;
sum(N, Acc) -> sum(N - 1, Acc + N).
main() -> sum(5, 0).
