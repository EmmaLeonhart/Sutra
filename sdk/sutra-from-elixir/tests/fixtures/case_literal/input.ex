defmodule M do
  def classify(n) do
    case n do
      1 -> 100
      2 -> 200
      _ -> 300
    end
  end

  def main do
    classify(2)
  end
end
