defmodule M do
  def add(a, b), do: a + b
  def double(x), do: x * 2

  def main do
    5 |> add(3) |> double()
  end
end
