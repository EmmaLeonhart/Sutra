defmodule M do
  def f(0, acc), do: acc
  def f(1, acc), do: acc + 100
  def f(n, acc), do: f(n - 1, acc + n)
  def main(), do: f(3, 0)
end
