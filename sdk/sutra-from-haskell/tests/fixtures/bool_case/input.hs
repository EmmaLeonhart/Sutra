f :: Bool -> Int
f b = case b of
  True -> 10
  False -> 20

main :: Int
main = f True
