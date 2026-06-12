defmodule Classifier do
  def classify(n) do
    if n > 0 do
      100
    else
      200
    end
  end

  def main do
    classify(5)
  end
end
