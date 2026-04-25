# Vectors: math vs computer science misconception

**Human:**

my gf thought vectors were an abstract computer science object and not math stuff

---

**Claude:**

Ha, that's a common mix-up! Vectors actually originate in mathematics and physics — they're fundamentally just quantities that have both a **magnitude** and a **direction** (like velocity or force).

The computer science concept of a "vector" (like `std::vector` in C++ or vectors in linear algebra libraries) is really just borrowing the math term, usually because those data structures are used to represent mathematical vectors or because they behave like ordered sequences (which map to coordinate vectors).

So the math came first:

- **Physics/geometry**: a vector is an arrow in space — e.g., "5 m/s northeast"
- **Linear algebra**: vectors are elements of a vector space — ordered lists of numbers like (3, 4) or (x, y, z)
- **CS**: borrowed the term for array-like structures, and also uses vectors heavily in ML (word vectors, embedding vectors, etc.)

Your GF isn't alone though — if you learn programming before math, you encounter the CS version first and it's easy to think of it as a purely computational idea. The connection becomes clearer once you get into linear algebra.

