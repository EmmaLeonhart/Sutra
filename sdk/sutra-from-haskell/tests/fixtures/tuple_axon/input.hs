addPair :: (Int, Int) -> Int
addPair p = fst p + snd p

main :: Int
main = addPair (5, 8)
