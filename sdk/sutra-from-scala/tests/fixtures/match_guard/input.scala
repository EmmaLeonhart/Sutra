def classify(n: Int): Int = n match {
  case 0 => 100
  case x if x > 0 => x * 10
  case _ => 300
}

def main(): Int = classify(6)
