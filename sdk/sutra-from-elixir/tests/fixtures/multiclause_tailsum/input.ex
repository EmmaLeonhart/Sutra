defmodule M do
  def sum(0, acc), do: acc
  def sum(n, acc), do: sum(n - 1, acc + n)

  def main() do
    sum(5, 0)
  end
end
