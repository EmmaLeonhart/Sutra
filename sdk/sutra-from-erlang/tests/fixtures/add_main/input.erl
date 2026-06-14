-module(add_main).
-export([add/2, main/0]).

add(A, B) -> A + B.

main() -> add(7, 9).
