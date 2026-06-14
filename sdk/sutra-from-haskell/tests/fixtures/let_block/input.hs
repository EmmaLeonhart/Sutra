g :: Int -> Int
g x = let a = x + 1
          b = a * 2
      in a + b

main :: Int
main = g 5
