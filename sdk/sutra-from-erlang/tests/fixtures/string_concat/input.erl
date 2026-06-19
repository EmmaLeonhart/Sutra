-module(m).
-export([main/0]).
cat(A, B) -> A ++ B.
classify(S) -> case S of "foobar" -> 100; _ -> 200 end.
main() -> classify(cat("foo", "bar")).
