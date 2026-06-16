data Wrap = Wrap Int Int

addw :: Wrap -> Int
addw w = let (Wrap a b) = w in a + b

main :: Int
main = addw (Wrap 5 8)
