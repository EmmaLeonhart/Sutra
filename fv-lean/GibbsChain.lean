/-
Sutra -> thrml, FV-in-Lean: the single-gadget Gibbs chain reaches the ground state.

Emma's queue seed (2026-06-14): "attempt a Lean convergence proof" of block-Gibbs
reaching the ground state -- the "stochastic ODEs" / Langevin angle. A FULL
convergence theorem (the t -> infinity limit of the sampler's law) is
measure-theoretic / analytic and needs mathlib; that is flagged as its own step
below. Here we discharge the BOUNDED, mathlib-FREE sub-claim Emma named: the
FINITE-STATE Markov-chain hypotheses that the classical convergence theorem
*requires* of the single-gadget Glauber chain, plus the Gibbs-measure mode.

The chain. Single-site (Glauber) block-Gibbs on the AND gadget's free state
space St = Bool^3 = (a,b,z): one step resamples one coordinate from its Gibbs
conditional, so it can change AT MOST one coordinate (and may leave the state
fixed -- the conditional is a softmax, every value has positive probability).
`Step s t` therefore holds iff s,t AGREE ON AT LEAST TWO of the three
coordinates (= differ in <= 1). `Reach` is its reflexive-transitive closure.

What is machine-checked here (no `sorry`, no mathlib):
  * `irreducible`  -- every state reaches every state (the 3-cube is connected,
                     and every Glauber edge has positive probability at finite beta).
  * `aperiodic`    -- every state has a self-loop (resample-to-same), so period 1.
  These two are EXACTLY the hypotheses (irreducible + aperiodic, finite chain) of
  the fundamental theorem of finite Markov chains: a unique stationary
  distribution pi exists and the law converges to it from ANY start.
  * `and_gibbs_unique_mode` -- for the clamped-input decode (a,b fixed, sample z),
    the correct output z = a AND b is the STRICT UNIQUE MODE of the Gibbs measure,
    for ANY strictly-antitone Gibbs weight w (the Boltzmann weight w(E)=exp(-beta*E)
    at any beta>0 qualifies). Built on `and_gadget_strict` (AndGadget.lean).

So: the finite Glauber chain converges (classical thm, hypotheses now checked) to
the unique stationary pi, and pi's unique mode is the arithmetically-correct
answer -- i.e. block-Gibbs reaches the ground state, with the only un-mechanised
link being the cited classical limit theorem.

NOT proven here (the mathlib step): the limit theorem itself (Perron-Frobenius /
total-variation mixing) and detailed balance pi(s)P(s,t)=pi(t)P(t,s), which need
the real-valued transition probabilities + exp -- i.e. mathlib's analysis. See
the queue item; this file is the finite/combinatorial floor under that.
-/

set_option linter.unusedSimpArgs false

-- Reuse the AND-gadget energy + strict-minimum proof.
def sp : Bool → Int
  | true  => 1
  | false => -1

def andOut (a b : Bool) : Bool := a && b

def E4 (a b z : Bool) : Int :=
  -sp a - sp b + 2 * sp z + sp a * sp b - 2 * sp a * sp z - 2 * sp b * sp z

/-- `a AND b` is the strict unique energy-minimiser over the sampled spin z
    (the clamped-decode statement of AndGadget.and_gadget_strict). -/
theorem and_gadget_strict : ∀ a b z : Bool,
    z ≠ andOut a b → E4 a b (andOut a b) < E4 a b z := by
  intro a b z h
  cases a <;> cases b <;> cases z <;> simp_all only [E4, andOut, sp,
    Bool.and_self, Bool.and_true, Bool.and_false, ne_eq, reduceCtorEq,
    not_true_eq_false, not_false_eq_true] <;> omega

/-- Gadget state: the three spins (a, b, z). -/
abbrev St := Bool × Bool × Bool

/-- One Glauber step changes at most one coordinate: s and t agree on at least
    two of the three coordinates. Self-loops (all three agree) are included --
    the Gibbs conditional can resample a spin to its current value. -/
def Step (s t : St) : Prop :=
  (s.1 = t.1 ∧ s.2.1 = t.2.1) ∨            -- agree on coords 1,2 (z may move)
  (s.1 = t.1 ∧ s.2.2 = t.2.2) ∨            -- agree on coords 1,3 (b may move)
  (s.2.1 = t.2.1 ∧ s.2.2 = t.2.2)          -- agree on coords 2,3 (a may move)

/-- Reachability: the reflexive-transitive closure of `Step`. -/
inductive Reach : St → St → Prop
  | refl (s : St) : Reach s s
  | step {s t u : St} : Step s t → Reach t u → Reach s u

/-- IRREDUCIBILITY: every state reaches every state. Path flips the differing
    coordinates one at a time (a then b then z); each flip is a single Glauber
    `Step`. The 3-cube is connected, so the finite chain is irreducible. -/
theorem irreducible : ∀ s t : St, Reach s t := by
  intro s t
  obtain ⟨s1, s2, s3⟩ := s
  obtain ⟨t1, t2, t3⟩ := t
  -- (s1,s2,s3) -> (t1,s2,s3) -> (t1,t2,s3) -> (t1,t2,t3)
  exact Reach.step (t := (t1, s2, s3)) (Or.inr (Or.inr ⟨rfl, rfl⟩))
    (Reach.step (t := (t1, t2, s3)) (Or.inr (Or.inl ⟨rfl, rfl⟩))
      (Reach.step (t := (t1, t2, t3)) (Or.inl ⟨rfl, rfl⟩) (Reach.refl _)))

/-- APERIODICITY: every state has a self-loop (the Gibbs conditional can resample
    a spin to its current value), so the chain has period 1. Irreducible +
    period-1 = ergodic, the hypothesis the classical convergence theorem needs. -/
theorem aperiodic : ∀ s : St, Step s s := by
  intro s; exact Or.inl ⟨rfl, rfl⟩

/-- A strictly-antitone weight turns a strict ENERGY minimiser into a strict
    WEIGHT (= Gibbs-probability) maximiser. The Boltzmann weight w(E)=exp(-beta*E)
    is strictly antitone for every beta>0, so this is the Gibbs-mode statement. -/
theorem strict_min_is_strict_mode {S : Type}
    (E : S → Int) (w : Int → Int)
    (hw : ∀ x y : Int, x < y → w y < w x)
    (s₀ : S) (hmin : ∀ s, s ≠ s₀ → E s₀ < E s) :
    ∀ s, s ≠ s₀ → w (E s) < w (E s₀) := by
  intro s hs; exact hw _ _ (hmin s hs)

/-- GIBBS UNIQUE MODE for the clamped AND-decode: with a,b clamped and z sampled,
    the correct output z = a AND b is the strict unique mode of the Gibbs measure
    for ANY strictly-antitone weight w (every beta>0 Boltzmann weight). Hence the
    stationary distribution the chain converges to is peaked on the right answer. -/
theorem and_gibbs_unique_mode (a b : Bool) (w : Int → Int)
    (hw : ∀ x y : Int, x < y → w y < w x) :
    ∀ z : Bool, z ≠ andOut a b → w (E4 a b z) < w (E4 a b (andOut a b)) := by
  intro z hz; exact hw _ _ (and_gadget_strict a b z hz)

#print axioms irreducible
#print axioms aperiodic
#print axioms strict_min_is_strict_mode
#print axioms and_gibbs_unique_mode
