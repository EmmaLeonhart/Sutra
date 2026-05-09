// Stateful counter pattern: a class instance whose state is mutated
// inside a while loop via a void method call. This exercises:
//   - Class with parameter properties + void method + value method
//   - `c.increment();` as a statement (Sutra augments to `c =
//     Counter_increment(c)` so c rebinds inside the loop body)
//   - `!c.isDone()` in the while condition (unary not + method call)
//   - Loop hoisting that picks up `c` as a state param and writes
//     it back to the outer scope after the loop returns

class Counter {
    constructor(public count: number) {}
    increment(): void { this.count = this.count + 1; }
    isDone(): boolean { return this.count >= 5; }
}

function run_to_five(): number {
    const c: Counter = new Counter(0);
    while (!c.isDone()) {
        c.increment();
    }
    return c.count;
}

function main(): number {
    return run_to_five();
}
