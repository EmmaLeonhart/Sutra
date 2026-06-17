defmodule M do
  def fac(0), do: 1
  def fac(n), do: n * fac(n - 1)

  def main() do
    fac(5)
  end
end
