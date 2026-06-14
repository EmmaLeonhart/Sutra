f :: Int -> Int
f x = y + z
  where y = x + 1
        z = x * 2

main :: Int
main = f 10
