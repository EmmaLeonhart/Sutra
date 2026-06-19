defmodule M do
  def cat(a, b) do
    a <> b
  end
  def classify(s) do
    if s == "foobar" do
      100
    else
      200
    end
  end
  def main(), do: classify(cat("foo", "bar"))
end
