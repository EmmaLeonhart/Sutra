// Loop transpilation: a side-effect-heavy `for` body becomes a
// tail-recursive loop function whose state is an axon carrying
// every variable the body references.

int sum_to_ten() {
    int sum = 0;
    for (int i = 0; i < 10; i++) {
        sum += i;
    }
    return sum;
}
