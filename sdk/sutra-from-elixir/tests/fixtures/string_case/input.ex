defmodule M do
  def classify(s) do
    case s do
      "foo" -> 10
      "bar" -> 20
      _ -> 30
    end
  end
  def main(), do: classify("foo") + classify("bar") + classify("baz")
end
