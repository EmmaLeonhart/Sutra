case class Outer(a: Int, pos: (Int, Int))

def g(o: Outer): Int = {
  val Outer(a, (x, y)) = o
  a + x + y
}

def main(): Int = g(Outer(5, (8, 3)))
