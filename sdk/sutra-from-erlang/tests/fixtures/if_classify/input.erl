-module(if_classify).
-export([classify/1, main/0]).

classify(N) -> if N > 0 -> 100; true -> 200 end.

main() -> classify(5).
