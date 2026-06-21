f :: Int -> Int
f n
  | n == 0    = 1
  | n == 1    = 5
  | otherwise = n * f (n - 1)

main :: Int
main = f 5
