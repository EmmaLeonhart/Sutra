// Struct-as-axon transpilation: pass a struct to a function, read
// fields by name. Expected lowering: each field becomes an axon key,
// `p.x` becomes `p.item("x")`, and the empty `Axon p;` constructor
// followed by `add` calls reproduces the C aggregate initializer.

struct Point {
    int x;
    int y;
};

int distance_squared(struct Point p) {
    return p.x * p.x + p.y * p.y;
}

int main() {
    struct Point p = { .x = 3, .y = 4 };
    return distance_squared(p);
}
