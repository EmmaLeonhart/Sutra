case class Point(x: Int, y: Int)

def sum(p: Point): Int = p match {
  case Point(a, b) => a + b
}

def main(): Int = sum(Point(5, 8))
