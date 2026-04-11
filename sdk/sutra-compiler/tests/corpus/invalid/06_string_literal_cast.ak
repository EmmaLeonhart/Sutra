// Expected error: AKA0111 - casting a string literal to a vector.
// String to vector must go through embed(), not a cast.

function vector Bad() {
    return (vector) "cat";
}
