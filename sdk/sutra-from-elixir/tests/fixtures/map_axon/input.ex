defmodule Geo do
  def sum2(p) do
    p.x + p.y
  end

  def main do
    sum2(%{x: 5, y: 8})
  end
end
