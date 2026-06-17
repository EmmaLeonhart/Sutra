fac :: Int -> Int
fac 0 = 1
fac n = n * fac (n - 1)

main :: Int
main = fac 5
