// Arrow functions assigned to a `const` (or `let`) hoist to a Sutra
// named function. Sutra has no anonymous-function surface, so the
// LHS variable name becomes the function's Sutra name. Both the
// single-expression form (`(x) => x * 2`) and the statement-block
// form (`(x) => { return x * 2; }`) are supported.

const double = (x: number): number => x * 2;

const greet = (name: string): string => {
    const greeting: string = "hello ";
    return greeting;
};

function main(): number {
    return double(21);
}
