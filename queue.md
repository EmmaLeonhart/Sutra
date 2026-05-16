# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

---

## super active

Earlier on, you basically just kind of completely lied to me and engaged in substrate leaks. I don't really know exactly what is going on right now, because I don't really know exactly what's going on right now, because of the fact that you lied to me and then it was a gigantic fucking mess.

I have my clear mathematical vision as to how it is that all these things would run. I'm not 100% sure how far we actually are through these things. I'm not sure at all how far we are through these things. I'm not really sure at all, meaningfully, how far through these things we are.

Just check the most recent edit summary for math.su, and also check the stuff I added, because that's my actual vision form. I think it probably will basically have its cosine and sine over an algebraic exponential, but it's still roughly in the same ballpark of stuff. The entire thing here is that we are not trying to get the answer, just to be clear. Getting the mathematical answer isn't really the goal. Getting the mathematical answer is not the right thing to do here, just to be clear.

I think that the entire scalar class is just substrate breaks, but the point isn't to get the answer to the math questions. We want the answer to the math questions, but the point here is to actually represent the math behind it.

There was a massive amount of chats where I was talking about mathematical definitions that were being used. There's a tonne of stuff where I was talking about mathematical definitions that were being used in the programming, like the way that you use an exponential lookup table to do all these other things. I don't know what exactly you did. I feel like you just kind of decided, "Oh, numpy uses these mathematical definitions, therefore I'm going to use numpy." That isn't what I wanted you to do. That isn't what I want you to do. What I wanted you to do was too simple: to make all this stuff clear and native within Sutra so that it essentially has the literate programming style of it. We should probably be specifying that this is a literate programming style, because I think this actually is a thing that might be recognised as the logic behind the operations. This might actually be recognised as the logic behind the operations if we explain this stuff now. There's a kind of literate programming style of basically every single thing eventually reducing down to very clearly defined mathematical proofs, which are basically like we're kind of citing the proof in the comments before the thing or like 

My idea here is we store three transcendental numbers.
- We store tau through a set binding point in the runtime.
- We store tau in a set binding point during the runtime.
- We also store our cross-talk exploiting logarithm table and exponential table.


It would be weirdly conceivably possible, maybe in the future, to even make it so the exponential and logarithm are the same thing, but for now they are separate.

I was extremely excited when you claimed to have been able to successfully implement the cross-talk exploiting lookup tables. I don't know if you even ever actually did so or if you just lied. I'd be very, very sad if that was the case, but I have to accept it. 

Yeah, so something to note here is that I think the queue.md here has not been properly used as a queue.md. It's being used a lot more like a generic status thing, and as a result it accumulates CRUD and stops being used properly, especially since it explicitly is supposed to be using the tool function. We're supposed to be generally avoiding this particular issue here.

Now I want to talk about sine and cosine. My view now is that I basically think cosine is distinct enough that it really needs to be its own thing, its own transcendental function, because it's much more complicated when you look at the imaginary output of the cosine. We'll be having to implement the imaginary output of the cosine geometrically too, and also basically all tanh stuff. It really has to be geometric, as stated earlier, because if we are doing so with substrate leaks, then it just kind of completely destroys the whole thing.

I also want you to specifically do an audit on whether there was a substrate leak with the tanh in the GPU stuff. I hope that this is made clear. It's kind of to be clear, and I hope this is made clear, although if it is made clear, please, for the love of god, put an explicit notification at the very front of the website, at the very home page or something, saying that the thing is a GPU pro. That is, whatever shortcut we made is an actual real GPU primitive, but it's possible it was this, and if you were going back to NumPy, you explained it so fucking poorly that I thought that you were going back to NumPy.

We have all this stuff because we're more or less trying to use solely GPU primitives for our math stuff, including a polynomial fuzzy logic and stuff like that. Just keep this in mind, and you need to face it. A lot of the information that I feel like you might think is getting to me isn't getting to me because I'm not reading enough of it, so you need to somehow give me a prominent notice. Maybe you could give me a phone notification, or maybe you could put a bit of a notification on our website at the very top of the GitHub pages that says that all our math is reducible to these different GPU primitives. The thing is, the GPU primitives also have to be ones that explicitly can be run in the classic SIMD fashion. That is a critical part of it. If the GPU is somehow able to do a regular branch where it just stops all its operations to do it, then, of course, you don't fucking do it, but I think tanh is in GPUs. It is possible, I don't think it's very likely. It's possible that you just created a whole thing, that you just created this gigantic mess of hallucinations and shit because you hallucinated that you lied to me. 

---

## tanh-audit answer (the explicit ask) — ANSWERED + VERIFIED

Yes, tanh leaked the substrate pre-2026-05-15 (`float(x)` host
return). Fixed in `21a9ff77`; **independently re-verified this run**
(read emitted code, ran it → `torch.Tensor` return matching
`math.tanh`, 0 leak signatures in the emitted `_st..floor` block).
The GPU ops in the chain (`matmul`/`clamp`/`round`/elementwise)
are all SIMD-class, no host branch. Full record:
`planning/findings/2026-05-15-tanh-audit-and-compiler-restore.md`.
The website notice the user asked for shipped (`2d821b7d`).

A side-effect found and fixed first: `math.su` had a Java-syntax
vision block that was a hard parse error — **the compiler was 100%
down for every program**. Restored (commit `900036df`), verified
(transcendentals 3/20-subtests, corpus+loader 15/103, smoke PASS).

---

## Recently shipped (detail in git log / findings, not re-listed here)

- Website homepage SIMD-GPU-primitive notice — done, `2d821b7d`
  (task #11). Survives the domain change to sutra.emmaleonhart.com
  (the notice is in `docs/index.md`, domain-independent).
- `substrate_leak_sweep.py` CI gate — done + observed green
  (`1 passed in 1738s`, 67 programs, 0 leaks; task #14). Speed
  refinement (≈29 min → slow/nightly) is the only follow-on.
- Transcendentals rewritten to the DOCUMENTED vision — `ecf1c4cd`
  / `744ec95e`. Canonical d-dim synthetic-axis complex (same repr
  as `complex_mul`); `exp(z)=realExp(z)⊗imaginaryExp(z)`,
  `cos=real(cexp(iθ))`, `sin=imag(cexp(iθ))`; verified vs ground
  truth (12 real + 3 complex incl. `cexp(iπ)=-1`, `cexp(1+iπ/2)=ie`).
  This **resolved prerequisite (a)** of the literate-math item.

## Active queue (mirrored to the task tool)

### 1. Literate math — make the `.su` bodies the executable reduction

The user's #1 vision: the `.su` method bodies ARE the beta-reduction,
not `intrinsic` + docstring. Status of the three prerequisites:
  (a) unify the complex representation — ✅ DONE 2026-05-15
      (`ecf1c4cd`). Canonical d-dim complex; `cexp` =
      `complex_mul(realExp, imaginaryExp)`; verified vs ground
      truth. The length-2 deviation is gone.
  (b) substrate-pure `.real`/`.imaginary` projection — ✅ OBVIATED.
      `realExp`/`imaginaryExp` now project the real/imag axis
      *internally* (one-hot dot, substrate-pure), so the literate
      body is `return realExp(z) * imaginaryExp(z)` with NO
      `.real`/`.imaginary` member access needed.
  (c) namespaced-stdlib inlining so `Math.exp(z)` resolves the
      `.su` body — **REMAINS**, now unblocked. ~10-line inliner
      change (resolve `Call(MemberAccess(Math, m))` against the
      stdlib table) + write the math.su bodies as bare-sibling
      reductions (`exp(z){ return realExp(z)*imaginaryExp(z); }`,
      `cos(z){ return cexp(...) ... }` etc.). Verify end-to-end
      (test_transcendentals + complex ground truth + corpus +
      smoke + leak grep) before marking done; revert if it does
      not fully verify (the discipline held last time). Task #12.

### 2. Audit.md REAL LEAK list — 5 of 8 resolved+verified; 3 structural left

`Audit.md` is the running substrate-leak catalogue (todo.md points
at it). Status after the 2026-05-15 autonomous run (each fix
individually verified — 0 code leak signatures + the relevant
test suite/ground-truth before its Audit line was struck):

- ✅ #1 `rotate_slot`/Givens — the eigenrotation off host floats
  (the worst leak). Substrate-pure cos/sin + 0-d tensor scatter.
- ✅ #2 `defuzzify_trit` — host scalar loop → codegen-time 10-step
  unroll of substrate `self.exp`, matches the documented algorithm
  to ≤1.4e-4.
- ✅ #6 `complex_div` — was already resolved; stale line ref
  corrected (1907 is `js_truthy`, a JS-interop carve-out).
- ✅ #7 `argmax_cosine` zero-norm — host `if float(q_norm)` →
  eps-guarded `_torch.where`.
- ✅ #8 `slot_store` — `float(scalar)` → `_st()`; the other two
  #8 sites documented as legitimate boundaries (structural slot
  index; literal lift).

**Still open — structural, larger, deliberately NOT faked:**

- #3 Promise `await_value` host `for _ in range(100)` — the
  substrate `while_loop` two-channel halt vector
  (`planning/sutra-spec/promises.md`); overlaps queue Promises
  work. Bounded by needing the halt-vector lowering, not a
  one-liner.
- #4 generic loop runtime `for _t in range(max_iters)` — the
  iteration mechanism `loop`/`while` lower to. Spec says
  `state ← R·state` on the substrate; #1 (rotate_slot) is now
  pure so the eigenrotation primitive it should bind to exists,
  but replacing the host driver loop is a control-flow-lowering
  rework with high regression surface. Do it deliberately, with
  the loop-runtime test suite as the gate, not as a rushed
  autonomous edit.
- #5 string ops as host codepoint loops (length/index/concat) —
  vectorize over the synthetic-axis block; a real
  string-runtime rewrite.

Fix shape for all = the `21a9ff77` model (tensors in→tensor
ops→tensors out; saturate not raise). Task #13 (stays in
progress — 3 genuine leaks remain; not marked done).

### 4. Wire `substrate_leak_sweep.py` into CI — ✅ gate green (verified)

`sdk/sutra-compiler/tests/test_substrate_leak_sweep.py` is committed
and **observed passing**: `1 passed in 1738.41s` — it compiled all
67 corpus+examples `.su` programs and found 0 substrate-operator
leaks. The next binary-operator leak in a user program will now
fail this gate. Verified green this run, not on faith.

Remaining refinement (not a blocker, logged honestly): ~29 min
runtime makes it a slow/nightly job, not a per-PR gate as-is.
CI-practical options: compile once and reuse the `_VSA` runtime
across files, scope to corpus-only for per-PR + full nightly, or
`pytest.mark.slow`. The gate is real and clean today; this is
speed, not correctness.

---

### 3. Triage every open-question — ~90% are already clearly defined

Emma 2026-05-15: most "open design questions" are not actually open;
they're decided in the spec / todo.md / voice-chat-absorbed notes
and just never got marked resolved. This run proved the failure
mode first-hand — the unified-complex-`number` representation was
treated as an "open design gap" when it is fully specified in
`todo.md` §"Transcendental functions — design absorbed from voice
chat" (`exp(z)=exp(re z)·(cos(im z)+i·sin(im z))`, canonical
d-dim synthetic-axis complex, two lookup leaves). Reading the
vision instead of declaring it open is the standing requirement
([[feedback-check-what-is-open-before-pitching-blocker]]).

Deliverable: go through every file in `planning/open-questions/`
(22 docs) **and** `planning/sutra-spec/open-questions.md` (162
lines) and give each a one-line verdict at the top:

- **RESOLVED** — decided; cite where (spec file / todo.md section /
  finding / dated commit). Move the doc's substance to the spec if
  it isn't already there; the open-question file becomes a
  pointer.
- **GENUINELY OPEN** — state the precise undecided sub-question in
  one sentence, and what evidence/decision would close it. Most
  will NOT be this.
- **STALE** — premised on a superseded design (e.g. numpy-backend-
  as-substrate, fly-brain, tier framing). Mark and delete or
  archive like `_archived-numpy-inheriting-from-flybrain.md`.

Work it as a real queue item (mirrored to the task tool), one
doc per pass, committing the verdicts. The output is a planning
surface that says exactly what is and isn't decided — so no
future session repeats this run's mistake. Task #15.

## Parked

- C → Sutra transpiler skeleton (`sdk/sutra-from-c/`): parked
  2026-05-08, stays in tree, do not delete.
- Yantra (the OS) is downstream of the TS transpiler; its own repo
  (`../Yantra/`) with its own queue. Sutra's queue ends at the
  transpiler.
- Promises Stage-3 closure capture, container method dispatch,
  multi-statement try/catch: longer-horizon, in `todo.md`.
- TS transpiler closeout (module imports, multi-program axon): the
  substantive pieces shipped; remaining polish in `todo.md`.

## Pointers

- Substrate-leak catalogue: `Audit.md` (work REAL LEAK first).
- Longer-horizon agenda: `todo.md`.
- Findings (dated, incl. this session's): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Devlog (full history): `DEVLOG.md`.
- Yantra: `../Yantra/`.
