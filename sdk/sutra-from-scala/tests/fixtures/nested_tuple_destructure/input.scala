def f(t: (Int, (Int, Int))): Int = {
  val (a, (b, c)) = t
  a + b + c
}
def main(): Int = f((5, (8, 3)))
