-module(guard_dispatch).
-export([grade/1, main/0]).

grade(N) when N > 90 -> 100;
grade(N) when N > 50 -> 50;
grade(_N) -> 0.

main() -> grade(95) + grade(70) + grade(20).
