defmodule M do
  def sel(flag, t) when flag > 0 do
    {a, b} = t
    a + b
  end
  def sel(_flag, _t) do
    0
  end

  def main() do
    sel(1, {5, 8})
  end
end
