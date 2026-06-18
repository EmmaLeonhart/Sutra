case class Inner(x: Int, y: Int)
case class Outer(inner: Inner, z: Int)

def sum(o: Outer): Int = {
  val Outer(Inner(a, b), c) = o
  a + b + c
}

def main(): Int = sum(Outer(Inner(5, 8), 3))
