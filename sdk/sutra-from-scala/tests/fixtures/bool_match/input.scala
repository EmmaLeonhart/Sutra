def f(b: Boolean): Int = b match {
  case true => 10
  case false => 20
}

def main(): Int = f(true)
