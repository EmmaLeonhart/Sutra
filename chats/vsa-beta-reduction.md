# Beta reduction in VSA lambda calculus

**Human:**

this does talk about beta reduction in VSA lambda calculus right or am I looking for a different paper

**Claude:**

You're mostly right, but it's worth being precise about what the paper actually does.

The paper does implement **lambda expressions in a VSA**, and the recursive definitions in equations (9) and (10) do describe what is effectively **substitution** — which is the core operation of beta reduction (replacing formal parameters with actual arguments). So functionally, yes, it's describing how to perform beta reduction in vector space.

However, the paper doesn't use the term "beta reduction" explicitly, and it's not framed in lambda calculus terms per se — it's framed in **Lisp 1.5 terms**. The lambda definitions are given as pattern-matching recursive rules over VSA operations rather than as a formal treatment of the lambda calculus reduction rules (α, β, η).

A few specific things to note:

- The paper handles **alpha renaming** explicitly (the relabel function, discussed around equation 9), which guards against variable capture
- The substitution logic in λs (equation 10) is doing the structural work of beta reduction — walking the expression tree and replacing occurrences of parameters with argument values
- It's **curried**, so multi-argument application is handled sequentially

**If you're looking for a paper that treats VSA lambda calculus more directly in lambda calculus terminology**, you might want to look at Smolensky (1990), which is cited here and deals with tensor product representations of symbolic structures more formally.

So: right paper, right intuition — just framed in Lisp vocabulary rather than lambda calculus vocabulary.

**Human:**

so this one is good?

**Claude:**

Yes, this is a much better fit for what you were originally looking for. Smolensky (1990) directly addresses variable binding in a vector/connectionist setting, which is the foundational operation underlying beta reduction.

Specifically, the relevant parts are:

**Section 3.7.2** on LISP binary tree operations (car, cdr, cons) shows how these operations are represented as linear transformations on the tensor product space. This is directly relevant because beta reduction in lambda calculus is essentially substitution, and substitution requires knowing what value is bound to what variable — exactly the unbinding problem Smolensky formalizes.

**Section 3.1** on unbinding is the closest thing to a formal treatment of what happens during substitution: given a composed representation, how do you extract the filler (value) associated with a particular role (variable)?

The key difference from the Tomkins-Flanagan & Kelly paper is that Smolensky works with **tensor products** rather than holographic reduced representations (circular convolution), and he's primarily interested in the **representational** question rather than implementing a full interpreter. So Smolensky gives you the math of how variable binding and unbinding work in vector space, while the first paper actually runs it as a Lisp interpreter.

Together they form a pretty complete picture: Smolensky lays the theoretical groundwork for VSA variable binding, and Tomkins-Flanagan & Kelly use that foundation (via HRRs specifically) to build something Turing-complete.
