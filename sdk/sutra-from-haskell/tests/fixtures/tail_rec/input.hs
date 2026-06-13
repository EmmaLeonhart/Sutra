sumTo :: Int -> Int -> Int
sumTo acc n = if n == 0 then acc else sumTo (acc + n) (n - 1)

main :: Int
main = sumTo 0 5
