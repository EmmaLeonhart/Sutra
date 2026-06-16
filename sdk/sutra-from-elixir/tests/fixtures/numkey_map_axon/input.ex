defmodule Geo do
  def sum2(p) do
    p[1] + p[2]
  end

  def main do
    sum2(%{1 => 5, 2 => 8})
  end
end
