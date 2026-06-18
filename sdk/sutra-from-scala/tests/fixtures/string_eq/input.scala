def classify(s: String): Int = if (s == "foo") 10 else 20
def main(): Int = classify("foo") + classify("bar")
