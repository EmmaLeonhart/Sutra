data Inner = Inner Int Int
data Outer = Outer Inner Int

f :: Outer -> Int
f w = case w of
  Outer (Inner a b) c -> a + b + c

main :: Int
main = f (Outer (Inner 5 8) 3)
