def classify(s: String): Int = s match { case "foo" => 10; case "bar" => 20; case _ => 30 }
def main(): Int = classify("foo") + classify("bar") + classify("baz")
