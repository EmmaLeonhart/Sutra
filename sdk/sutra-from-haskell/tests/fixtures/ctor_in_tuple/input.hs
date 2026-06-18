data Box = Box Int

f :: (Int, Box) -> Int
f t = let (a, Box b) = t in a + b

main :: Int
main = f (5, Box 8)
