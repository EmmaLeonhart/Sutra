defmodule Geo do
  def sum2(p) do
    p.x + p.y
  end

  def main do
    sum2(%Point{x: 6, y: 7})
  end
end
