data Wrap = Wrap (Int, Int)

g :: Wrap -> Int
g w = let (Wrap (a, b)) = w in a + b

main :: Int
main = g (Wrap (5, 8))
