defmodule M do
  def sum2(%Point{x: a, y: b}) do
    a + b
  end

  def main() do
    sum2(%Point{x: 5, y: 8})
  end
end
