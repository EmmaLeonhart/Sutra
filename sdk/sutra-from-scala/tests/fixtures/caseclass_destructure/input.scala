case class Point(x: Int, y: Int)
def sum(p: Point): Int = {
  val Point(a, b) = p
  a + b
}
def main(): Int = sum(Point(5, 8))
