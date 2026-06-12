case class Point(x: Int, y: Int)

def mk(a: Int, b: Int): Point = Point(a, b)

def getx(p: Point): Int = p.x

def sum2(p: Point): Int = p.x + p.y

def main(): Int = getx(mk(7, 9)) + sum2(Point(2, 3))
