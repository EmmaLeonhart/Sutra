defmodule M do
  def kind(x) when is_binary(x), do: 1
  def kind(x) when is_number(x), do: 2
  def kind(_x), do: 3

  def main do
    kind("a") * 100 + kind(5) * 10 + kind({7, 8})
  end
end
