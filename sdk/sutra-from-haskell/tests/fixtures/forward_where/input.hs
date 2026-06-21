f :: Int -> Int
f x = a + b
  where a = b + 1
        b = x * 2

main :: Int
main = f 10
