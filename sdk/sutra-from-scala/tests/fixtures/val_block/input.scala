def f(x: Int): Int = {
  val y = x + 1
  val z = y * 2
  z + x
}
def main(): Int = f(5)
