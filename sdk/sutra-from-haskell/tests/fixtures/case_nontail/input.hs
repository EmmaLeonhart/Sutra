f :: Int -> Int
f n = 1 + (case n of
             0 -> 100
             _ -> 200)

main :: Int
main = f 0
