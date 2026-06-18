sumTo :: Int -> Int -> Int
sumTo acc n
  | n == 0 = acc
  | n > 0  = sumTo (acc + n) (n - 1)

main :: Int
main = sumTo 0 5
