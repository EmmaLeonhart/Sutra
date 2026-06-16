addPair :: (Int, Int) -> Int
addPair t = let (a, b) = t in a + b

main :: Int
main = addPair (5, 8)
