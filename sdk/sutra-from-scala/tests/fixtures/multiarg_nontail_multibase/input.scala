def f(a: Int, b: Int): Int = if (a == 0) b else if (a == 1) b + 100 else a + f(a - 1, b)

def main(): Int = f(3, 10)
