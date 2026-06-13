classify :: Int -> Int
classify 0 = 100
classify 1 = 200
classify n = n * 10

main :: Int
main = classify 0 + classify 2
