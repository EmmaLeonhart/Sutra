classify :: String -> Int
classify s = case s of
  "foo" -> 10
  "bar" -> 20
  _ -> 30

main :: Int
main = classify "foo" + classify "bar" + classify "baz"
