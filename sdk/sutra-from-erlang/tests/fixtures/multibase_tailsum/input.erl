-module(multibase_tailsum).
-export([main/0]).

f(0, Acc) -> Acc;
f(1, Acc) -> Acc + 100;
f(N, Acc) -> f(N - 1, Acc + N).

main() -> f(3, 0).
