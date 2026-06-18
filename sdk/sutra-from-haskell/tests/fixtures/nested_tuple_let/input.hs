f :: (Int, (Int, Int)) -> Int
f t = let (a, (b, c)) = t in a + b + c

main :: Int
main = f (5, (8, 3))
