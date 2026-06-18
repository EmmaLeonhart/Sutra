f :: Int -> Int -> Int
f n acc
  | n == 0    = acc
  | n == 1    = acc + 100
  | otherwise = f (n - 1) (acc + n)

main :: Int
main = f 3 0
