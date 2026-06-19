defmodule M do
  def f(0), do: 1
  def f(1), do: 5
  def f(n), do: n * f(n - 1)
  def main(), do: f(5)
end
