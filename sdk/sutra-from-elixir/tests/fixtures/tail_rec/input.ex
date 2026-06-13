defmodule Rec do
  def sum_to(acc, n) do
    if n == 0 do
      acc
    else
      sum_to(acc + n, n - 1)
    end
  end

  def main do
    sum_to(0, 5)
  end
end
