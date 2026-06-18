defmodule M do
  def f(n, acc) when n > 0, do: f(n - 1, acc + n)
  def f(_, acc), do: acc
  def main(), do: f(5, 0)
end
