defmodule M do
  def sum2(%{x: a, y: b}) do
    a + b
  end

  def main() do
    sum2(%{x: 5, y: 8})
  end
end
