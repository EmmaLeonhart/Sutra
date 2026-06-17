-record(point, {x, y}).
fst(#point{x=X, y=Y}) -> X + Y.
main() -> fst(#point{x=5, y=8}).
