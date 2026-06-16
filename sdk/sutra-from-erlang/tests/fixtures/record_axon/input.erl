-module(record_axon).
-export([main/0]).
-record(point, {x, y}).

fst(P) -> P#point.x + P#point.y.

main() -> fst(#point{x=5, y=8}).
