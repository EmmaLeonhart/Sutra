defmodule M do
  def classify(s) do
    if s == "foo" do
      10
    else
      20
    end
  end
  def main(), do: classify("foo") + classify("bar")
end
