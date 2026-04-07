# Proof Sketch: Transformers as Finite-State Machines

## Formal Argument

### Theorem
A transformer-based language model with fixed parameters is a finite-state transducer and is therefore not Turing-complete.

### Proof Sketch

**Step 1: Finite state space.**
A transformer has a fixed architecture: *L* layers, *d*-dimensional residual stream, *H* attention heads per layer, and *b*-bit floating-point precision for all parameters and activations. At any point during inference, the complete internal state of the model is determined by:
- The residual stream activations across all positions: a matrix in R^{n × d}, where *n* is the (bounded) context length
- The attention pattern at each layer: *L* × *H* matrices in R^{n × n}

Since *n*, *d*, *L*, *H*, and *b* are all fixed at architecture time, the total number of distinguishable internal states is at most:

    |S| ≤ 2^(b × n × d × L)

This is astronomically large (e.g., for GPT-3 scale: ~2^(10^14)) but **finite**. By definition, a system with a finite set of internal states and deterministic transitions is a finite-state machine.

**Step 2: No external memory.**
A Turing machine requires an unbounded tape — external memory that can be extended arbitrarily during computation. A transformer has no such mechanism:
- Its "working memory" is the residual stream, fixed at width *d* and length *n*
- Its "long-term memory" is its parameters, fixed after training
- It cannot dynamically allocate new memory during inference

This means a transformer cannot, in principle, perform computations that require tracking an unbounded number of intermediate states. For any fixed transformer, there exists a logical formula (or a context-free language, or a recursive function) whose evaluation requires more state than the architecture provides.

**Step 3: Position in the Chomsky hierarchy.**
Merrill et al. (2022) prove a stronger result: transformers with hard attention (saturated attention, where softmax outputs converge to one-hot) are equivalent to constant-depth threshold circuits (the complexity class TC^0). TC^0 is a proper subset of NC^1 ⊂ P ⊂ RE, and in particular:
- TC^0 **can** compute: majority, addition, multiplication, sorting
- TC^0 **cannot** compute: general Boolean formula evaluation, context-free language recognition, or any problem requiring unbounded sequential computation

Hahn (2020) proves that self-attention cannot recognize certain formal languages, including Dyck-2 (balanced parentheses with two types) at unbounded depth, establishing an expressivity ceiling independent of model size.

**Step 4: Soft attention does not escape finiteness.**
One might object that real transformers use soft attention (continuous softmax), not hard attention, and that the continuous dynamics might achieve greater expressivity. Weiss, Goldberg, and Yahav (2021) formalize transformers as a programming language (RASP) and show that while soft attention permits richer computation per layer, the total computation remains bounded by the depth *L* and width *d*. Increasing *L* and *d* increases the size of the finite automaton but does not make it infinite.

**Step 5: Chain-of-thought as bounded unrolling.**
Chain-of-thought (CoT) prompting appears to give transformers sequential computation ability: the model generates intermediate tokens that serve as "scratch space." However:
- The total number of generated tokens is bounded by the context window *n*
- Each generation step is still a fixed-width transformation (the same *d*-dimensional residual stream)
- CoT unrolls sequential computation into the token dimension, but *n* is finite

This means CoT increases the effective depth of the computation graph from *L* to *L × n*, but the system remains finite-state. For any fixed (*L*, *d*, *n*), there exists a computation that requires *L × n + 1* sequential steps and therefore cannot be performed.

### Corollary: Embedding Spaces as Finite Representations
The embedding space used in RAG retrieval inherits these constraints. An embedding function *f: Σ* → R^d* maps the space of all possible text strings (countably infinite) into a *d*-dimensional real vector space. With *b*-bit precision, the codomain has at most 2^(b×d) distinguishable points. This means:

1. **Collisions are inevitable.** Infinitely many distinct strings must map to the same embedding vector (pigeonhole principle). When two semantically distinct propositions collide, the retrieval system cannot distinguish them.

2. **Logical structure is compressed, not absent.** Our experiments show that embedding spaces DO encode systematic logical structure — subjects, predicates, and objects compose approximately additively (§4.1), verbs act as consistent displacement vectors (§4.3), and compositionality is real but lopsided. The issue is not that logical structure is absent, but that it is **compressed with non-uniform fidelity**: entities receive 3.5× more representational capacity than predicates because the distributional training signal for entities is stronger.

3. **The VKG as external tape.** The Virtual Knowledge Graph is, formally, the external memory that the transformer lacks. It provides:
   - **Unbounded entity tracking:** The VKG can represent arbitrarily many entities and relationships, limited only by the input corpus, not by a fixed architectural parameter.
   - **Explicit relational structure:** Predicates have first-class representation as edge labels, not compressed into the residual subspace of entity embeddings.
   - **Compositional traversal:** Multi-hop reasoning is implemented as graph traversal (path-finding), not as a single fixed-depth forward pass.

## Key References

1. **Merrill, W., Sabharwal, A., & Smith, N. A. (2022).** "Saturated Transformers are Constant-Depth Threshold Circuits." *Transactions of the Association for Computational Linguistics*, 10, 843–856. — Proves that saturated (hard-attention) transformers compute exactly the functions in TC^0.

2. **Weiss, G., Goldberg, Y., & Yahav, E. (2021).** "Thinking Like Transformers." *Proceedings of ICML 2021*. — Formalizes transformers as the programming language RASP, showing that each layer computes a bounded set of operations over sequences.

3. **Hahn, M. (2020).** "Theoretical Limitations of Self-Attention in Neural Sequence Models." *Transactions of the Association for Computational Linguistics*, 8, 156–171. — Proves that self-attention cannot recognize bounded-depth Dyck languages, establishing a formal expressivity ceiling.

4. **Pérez, J., Barceló, P., & Marinkovic, J. (2021).** "Attention is Turing Complete." *Journal of Machine Learning Research*, 22(75), 1–35. — Shows that transformers WITH unbounded precision and unbounded computation steps are Turing-complete, but this requires infinite precision — precisely the condition that does not hold in practice.

## Implications for the Paper's Claims

The correct framing is NOT "embedding spaces cannot represent logical structure" (too strong — our experiments show they do represent some). It is:

**Embedding spaces encode logical structure with non-uniform fidelity, systematically under-representing relational/predicate structure relative to entity/topical structure, as a consequence of distributional training objectives. Furthermore, as finite-state representations, they cannot perform unbounded compositional reasoning — they can approximate it within a fixed computational budget but will fail for any logical chain that exceeds this budget. The VKG addresses both limitations: it gives predicates first-class representation and provides an external symbolic workspace for unbounded chain traversal.**

This framing is:
- Consistent with our experimental evidence (embeddings DO encode structure, just lopsidedly)
- Grounded in established theoretical results (Merrill, Weiss, Hahn)
- More precise than "can't represent logical structure"
- Connects the theoretical argument to the practical system
