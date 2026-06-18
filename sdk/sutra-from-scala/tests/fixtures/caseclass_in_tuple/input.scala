case class Box(v: Int)

def f(t: (Int, Box)): Int = {
  val (a, Box(v)) = t
  a + v
}

def main(): Int = f((5, Box(8)))
