f :: Int -> Int -> Int
f a b
  | a == 0    = b
  | a == 1    = b + 100
  | otherwise = a + f (a - 1) b

main :: Int
main = f 3 10
