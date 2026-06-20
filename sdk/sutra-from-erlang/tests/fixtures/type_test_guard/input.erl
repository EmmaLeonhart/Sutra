-module(m).
-export([main/0]).

kind(X) when is_number(X) -> 1;
kind(_X) -> 2.

main() -> kind(5) * 10 + kind("hello").
