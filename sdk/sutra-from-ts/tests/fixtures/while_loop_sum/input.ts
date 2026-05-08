// While-loop with reassigned state. `let` declarations lower to `slot`
// so the Sutra-side compiler treats them as mutable cells. The body
// uses an augmented assignment and a postfix increment; both desugar
// to plain assignments at lowering time.

function sum_up_to(n: number): number {
    let sum = 0;
    let i = 0;
    while (i < n) {
        sum += i;
        i++;
    }
    return sum;
}

function main(): number {
    return sum_up_to(10);
}
