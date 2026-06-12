def classify(n: Int): Int = n match {
  case 1 => 100
  case 2 => 200
  case _ => 300
}
def main(): Int = classify(2)
