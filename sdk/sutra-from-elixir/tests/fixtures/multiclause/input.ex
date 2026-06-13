defmodule M do
  def classify(0), do: 100
  def classify(1), do: 200
  def classify(n), do: n * 10

  def main do
    classify(0) + classify(2)
  end
end
