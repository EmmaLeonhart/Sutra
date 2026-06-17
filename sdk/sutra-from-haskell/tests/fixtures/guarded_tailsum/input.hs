sumTo :: Int -> Int -> Int
sumTo n acc
  | n == 0 = acc
  | otherwise = sumTo (n - 1) (acc + n)

main :: Int
main = sumTo 5 0
