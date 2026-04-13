# Real vector spaces explained

**Human:**

what is a real vector space

---

**Claude:**

A **real vector space** is a set VV
V whose elements (called *vectors*) can be added together and scaled by real numbers, subject to a specific list of rules.

## Formal Definition

A real vector space is a set VV
V equipped with two operations:

- **Addition:** u+v∈V\mathbf{u} + \mathbf{v} \in V
u+v∈V for any u,v∈V\mathbf{u}, \mathbf{v} \in V
u,v∈V
- **Scalar multiplication:** cv∈Vc\mathbf{v} \in V
cv∈V for any c∈Rc \in \mathbb{R}
c∈R, v∈V\mathbf{v} \in V
v∈V

satisfying these **8 axioms** for all u,v,w∈V\mathbf{u}, \mathbf{v}, \mathbf{w} \in V
u,v,w∈V and c,d∈Rc, d \in \mathbb{R}
c,d∈R:

| # | Axiom | Rule |
| --- | --- | --- |
| 1 | Commutativity | u+v=v+u\mathbf{u} + \mathbf{v} = \mathbf{v} + \mathbf{u}
u+v=v+u |
| 2 | Associativity of addition | (u+v)+w=u+(v+w)(\mathbf{u} + \mathbf{v}) + \mathbf{w} = \mathbf{u} + (\mathbf{v} + \mathbf{w})
(u+v)+w=u+(v+w) |
| 3 | Zero vector | ∃ 0∈V\exists\, \mathbf{0} \in V
∃0∈V such that v+0=v\mathbf{v} + \mathbf{0} = \mathbf{v}
v+0=v |
| 4 | Additive inverse | ∃ −v∈V\exists\, {-\mathbf{v}} \in V
∃−v∈V such that v+(−v)=0\mathbf{v} + (-\mathbf{v}) = \mathbf{0}
v+(−v)=0 |
| 5 | Multiplicative identity | 1⋅v=v1 \cdot \mathbf{v} = \mathbf{v}
1⋅v=v |
| 6 | Associativity of scaling | (cd)v=c(dv)(cd)\mathbf{v} = c(d\mathbf{v})
(cd)v=c(dv) |
| 7 | Distributivity over vectors | c(u+v)=cu+cvc(\mathbf{u} + \mathbf{v}) = c\mathbf{u} + c\mathbf{v}
c(u+v)=cu+cv |
| 8 | Distributivity over scalars | (c+d)v=cv+dv(c + d)\mathbf{v} = c\mathbf{v} + d\mathbf{v}
(c+d)v=cv+dv |

## Examples

- Rn\mathbb{R}^n
Rn — the most familiar example; nn
n-tuples of real numbers
- Rm×n\mathbb{R}^{m \times n}
Rm×n — the space of all m×nm \times n
m×n real matrices
- C([a,b])C([a,b])
C([a,b]) — continuous functions on an interval (vectors are functions!)
- Pn\mathcal{P}_n
Pn​ — polynomials of degree ≤n\leq n
≤n
- {0}\{\mathbf{0}\}
{0} — the trivial vector space containing only the zero vector

## Key Idea

The power of the definition is its **abstraction**: anything satisfying these 8 axioms inherits a huge body of theory — subspaces, bases, dimension, linear maps, eigenvalues — regardless of what the "vectors" actually are. Arrows in 3D space and functions on an interval are both vectors in this sense.

The word *real* simply means the scalars come from R\mathbb{R}
R. If they came from C\mathbb{C}
C instead, you'd have a *complex* vector space.

