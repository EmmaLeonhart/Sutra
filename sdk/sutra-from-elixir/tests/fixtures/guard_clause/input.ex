defmodule M do
  def grade(n) when n > 90, do: 100
  def grade(n) when n > 50, do: 50
  def grade(_n), do: 0

  def main do
    grade(95) + grade(70) + grade(20)
  end
end
