classify :: Int -> Int
classify n
  | n == 0 = 100
  | n == 1 = 200
  | otherwise = n * 10

main :: Int
main = classify 0 + classify 2
