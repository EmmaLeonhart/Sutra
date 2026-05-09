// TS array of primitives: `number[]` lowers to a Sutra `Array`
// type marker. Indexing (`arr[i]`) lowers as plain subscript; the
// `.length` property lowers to a Sutra `array_length(arr)` builtin
// that emits Python `len(arr)`. Array literals (`[1, 2, 3]`) emit
// as Python lists at runtime.

function sum_arr(arr: number[]): number {
    let total = 0;
    for (let i = 0; i < arr.length; i++) {
        total = total + arr[i];
    }
    return total;
}

function main(): number {
    return sum_arr([1, 2, 3, 4, 5]);
}
