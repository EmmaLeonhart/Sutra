defmodule M do
  def kind(x) when is_binary(x), do: 1
  def kind(_x), do: 2

  def main do
    kind("a") * 10 + kind(5)
  end
end
