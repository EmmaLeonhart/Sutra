# 2026-05-17 — Voice-vision capture: transcendental constants, cosine-as-own-function, GPU-primitive framing

**This is a verbatim relocation, not a summary.** It is the "super active"
block that had accumulated in `queue.md`. Per the chats-triage rule
(preserve the actual log, do not substitute a summary), the user's words
are reproduced below exactly as written. The queue.md item was removed in
the same commit and replaced with a pointer here plus the distilled,
still-live action items (see "Reconciliation" at the bottom — that part IS
editorial and is clearly marked as such).

---

## Verbatim (from queue.md `## super active`)

Earlier on, you basically just kind of completely lied to me and engaged in substrate leaks. I don't really know exactly what is going on right now, because I don't really know exactly what's going on right now, because of the fact that you lied to me and then it was a gigantic mess.

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

I also want you to specifically do an audit on whether there was a substrate leak with the tanh in the GPU stuff. I hope that this is made clear. It's kind of to be clear, and I hope this is made clear, although if it is made clear, please, for the love of god, put an explicit notification at the very front of the website, at the very home page or something, saying that the thing is a GPU pro. That is, whatever shortcut we made is an actual real GPU primitive, but it's possible it was this, and if you were going back to NumPy, you explained it so poorly that I thought that you were going back to NumPy.

We have all this stuff because we're more or less trying to use solely GPU primitives for our math stuff, including a polynomial fuzzy logic and stuff like that. Just keep this in mind, and you need to face it. A lot of the information that I feel like you might think is getting to me isn't getting to me because I'm not reading enough of it, so you need to somehow give me a prominent notice. Maybe you could give me a phone notification, or maybe you could put a bit of a notification on our website at the very top of the GitHub pages that says that all our math is reducible to these different GPU primitives. The thing is, the GPU primitives also have to be ones that explicitly can be run in the classic SIMD fashion. That is a critical part of it. If the GPU is somehow able to do a regular branch where it just stops all its operations to do it, then, of course, you don't do it, but I think tanh is in GPUs. It is possible, I don't think it's very likely. It's possible that you just created a whole thing, that you just created this gigantic mess of hallucinations because you hallucinated that you lied to me. 

---

## Reconciliation (editorial — added 2026-05-17, NOT the user's words)

Mapping each ask in the block to current git/findings reality, so the
queue carries only what is still live. Where something is claimed done,
the citation is given so it can be independently re-verified rather than
trusted.

- **"audit whether tanh leaked the substrate in the GPU stuff"** —
  ANSWERED + independently re-verified. tanh leaked pre-2026-05-15
  (`float(x)` host return); fixed `21a9ff77`; record at
  `planning/findings/2026-05-15-tanh-audit-and-compiler-restore.md`. The
  GPU ops in the chain (matmul/clamp/round/elementwise) are SIMD-class,
  no host branch.
- **"prominent website notice that the math is real SIMD-GPU
  primitives"** — shipped `2d821b7d` (homepage notice, domain-independent,
  survives the move to sutra.emmaleonhart.com).
- **"literate programming style; math.su source IS the beta-reduction;
  stop substituting numpy definitions"** — core delivered `ae269f6b`,
  `b9e11f5e`; transcendentals rewritten to the documented vision
  `ecf1c4cd`/`744ec95e`. Remaining is the Task #12 tail (cosmetic +
  test-gated migration), tracked in the queue.
- **STILL LIVE — "store three transcendental constants: tau at a runtime
  binding point; cross-talk-exploiting log table + exp table as the two
  leaves"** — needs explicit verification that the *shipped*
  transcendentals literally realize this (tau bound in the runtime; the
  two leaves are genuine cross-talk-exploiting lookup tables, not a
  libm/torch elementwise call). This is a real queue item — see queue.md
  § "Voice-vision live items" item 1 (added 2026-05-28).
- **STILL LIVE / NEW OPEN DESIGN QUESTION — "cosine needs to be its own
  transcendental function, not derived from the algebraic exponential;
  imaginary output of cosine implemented geometrically"** — this
  contradicts the just-shipped boundary where `cos = real(cexp(iθ))`,
  `sin = imag(cexp(iθ))`. It is a design change the user is asserting; it
  must be captured as an open question and decided with the user, NOT
  silently implemented or silently kept as-is. See
  `planning/open-questions/cosine-as-its-own-transcendental.md` and
  queue.md § "Voice-vision live items" item 2 (added 2026-05-28).
