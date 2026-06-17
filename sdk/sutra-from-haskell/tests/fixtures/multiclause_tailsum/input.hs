sum :: Int -> Int -> Int
sum 0 acc = acc
sum n acc = sum (n - 1) (acc + n)

main :: Int
main = sum 5 0
