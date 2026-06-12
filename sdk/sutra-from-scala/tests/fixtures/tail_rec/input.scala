def sumTo(acc: Int, n: Int): Int = if (n == 0) acc else sumTo(acc + n, n - 1)

def main(): Int = sumTo(0, 5)
