f :: Int -> Int -> Int
f acc n
  | n == 0 = acc
  | n == 1 = acc + 100
  | n > 1  = f (acc + n) (n - 1)

main :: Int
main = f 0 3
