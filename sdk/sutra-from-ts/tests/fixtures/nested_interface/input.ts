interface Inner { v: number; }
interface Outer { a: number; inner: Inner; }

function f(o: Outer): number {
  return o.a + o.inner.v;
}

function main(): number {
  const x: Outer = { a: 5, inner: { v: 8 } };
  return f(x);
}
