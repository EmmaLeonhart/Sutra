sel(Flag, T) when Flag > 0 ->
    {A, B} = T,
    A + B;
sel(_Flag, _T) ->
    0.
main() -> sel(1, {5, 8}).
