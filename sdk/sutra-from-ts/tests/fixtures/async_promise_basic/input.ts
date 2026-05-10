// TS async function with one await + chained-await variant.
// The transpiler should pass async/await/Promise<T> through verbatim
// to the Sutra surface forms; see planning/sutra-spec/promises.md.

async function fetch_label(query: string): Promise<string> {
    const r = await network_lookup(query);
    return r;
}

async function chained(q: string): Promise<string> {
    const first = await fetch_label(q);
    const second = await fetch_label(first);
    return second;
}
