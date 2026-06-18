def cat(a: String, b: String): String = a + b
def f(s: String): Int = if (s == "foobar") 100 else 200
def main(): Int = f(cat("foo", "bar"))
