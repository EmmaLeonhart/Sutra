defmodule T do
  def fst(p) do
    elem(p, 0) + elem(p, 1)
  end

  def main do
    fst({5, 8})
  end
end
