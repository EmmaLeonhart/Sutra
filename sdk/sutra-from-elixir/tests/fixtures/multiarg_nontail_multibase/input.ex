defmodule M do
  def f(0, b), do: b
  def f(1, b), do: b + 100
  def f(a, b), do: a + f(a - 1, b)
  def main(), do: f(3, 10)
end
