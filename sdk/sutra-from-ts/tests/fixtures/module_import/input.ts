// Importing module. Pulls `double` from `./helper` and calls it.
// The transpiler resolves the import at lower-time, recursively
// lowers helper.ts, and inlines the resulting Sutra declarations at
// the top of this file's output as a module preamble. `triple` is
// exported by helper.ts but unused here; the MVP still inlines it
// because we're not doing tree-shaking yet.

import { double } from "./helper";

function main(): number {
    return double(21);
}
