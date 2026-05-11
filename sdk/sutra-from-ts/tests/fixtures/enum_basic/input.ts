// TS enum lowering. The transpiler erases the enum declaration and
// inlines each `EnumName.Member` reference as the integer value the
// enum's prepass recorded. Members default to auto-incrementing
// from 0; an explicit `= N` assignment resets the counter.
//
// Enum-typed parameters (`c: Color`) lower to `int c` — the
// runtime carrier is a plain integer; the enum's "type" is purely
// a transpile-time tag for name lookup.

enum Status {
    Idle,           // 0 (default start)
    Running = 5,    // 5 (explicit)
    Done            // 6 (auto-increment from 5)
}

function classify(s: Status): number {
    return s + 100;
}

function main(): number {
    return classify(Status.Done);
}
