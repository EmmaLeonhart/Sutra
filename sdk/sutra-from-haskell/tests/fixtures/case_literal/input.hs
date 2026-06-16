classify :: Int -> Int
classify n = case n of
  0 -> 100
  1 -> 200
  _ -> 300

main :: Int
main = classify 1 + classify 0
