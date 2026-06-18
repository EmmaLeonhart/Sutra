defmodule M do
  def f(b) do
    case b do
      true -> 10
      false -> 20
    end
  end

  def main() do
    f(true)
  end
end
