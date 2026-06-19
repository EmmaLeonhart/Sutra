-module(m).
-export([main/0]).
classify(S) -> case S of "foo" -> 10; "bar" -> 20; _ -> 30 end.
main() -> classify("foo") + classify("bar") + classify("baz").
