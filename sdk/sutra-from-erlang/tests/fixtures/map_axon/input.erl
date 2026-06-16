-module(map_axon).
-export([main/0]).

sum2(P) -> maps:get(1, P) + maps:get(2, P).

main() -> sum2(#{1 => 5, 2 => 8}).
