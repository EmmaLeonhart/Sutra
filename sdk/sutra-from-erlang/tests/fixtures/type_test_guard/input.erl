-module(m).
-export([main/0]).

kind(X) when is_number(X) -> 1;
kind(X) when is_tuple(X) -> 2;
kind(_X) -> 3.

main() -> kind(5) * 100 + kind({7, 8}) * 10 + kind("hello").
