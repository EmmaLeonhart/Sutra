fac :: Int -> Int
fac n
  | n == 0 = 1
  | otherwise = n * fac (n - 1)

main :: Int
main = fac 5
