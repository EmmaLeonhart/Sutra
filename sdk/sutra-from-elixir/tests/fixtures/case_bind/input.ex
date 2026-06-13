defmodule M do
  def classify(n) do
    case n do
      0 -> 100
      x -> x * 10
    end
  end

  def main do
    classify(6)
  end
end
