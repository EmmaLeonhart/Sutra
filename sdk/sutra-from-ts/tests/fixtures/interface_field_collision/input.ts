// Two interfaces share a field NAME (`v`) with CONFLICTING types: A.v is a
// number, B.v is a string. The merged global field-type map collapses `v` to
// "JavaScriptObject" on the conflict, which would (wrongly) deny `a.v` its
// numeric `realvec` projection. Per-variable interface typing resolves each
// `x.v` in its own interface's field map: A.v -> realvec (number), B.v -> raw
// (string, feeds eq_synthetic). Without it, `a.v + 1` mis-lowers to js_add.

interface A {
    v: number;
}

interface B {
    v: string;
}

function fa(a: A): number {
    return a.v + 1;
}

function fb(b: B): number {
    if (b.v == "foo") {
        return 10;
    }
    return 20;
}

function main(): number {
    const x: A = { v: 5 };
    return fa(x);
}
