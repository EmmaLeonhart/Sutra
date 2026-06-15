data Expr = Lit Int | Neg Int

evalE :: Expr -> Int
evalE e = case e of
  Lit n -> n
  Neg n -> 0 - n

main :: Int
main = evalE (Lit 7) + evalE (Neg 5)
