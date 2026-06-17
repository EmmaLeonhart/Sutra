defmodule M do
  def fac(n) when n == 0, do: 1
  def fac(n), do: n * fac(n - 1)

  def main() do
    fac(5)
  end
end
