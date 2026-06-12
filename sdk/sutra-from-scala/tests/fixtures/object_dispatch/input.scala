object Calc {
  def add(a: Int, b: Int): Int = a + b
  def twice(x: Int): Int = add(x, x)
}

def main(): Int = Calc.add(7, 9) + Calc.twice(5)
