defmodule M do
  def sum2(t) do
    {a, b} = t
    a + b
  end

  def main() do
    sum2({5, 8})
  end
end
