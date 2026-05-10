# Outreach draft — Neural Computers (arxiv 2604.06425)

**Status:** DRAFT, not yet sent. Awaiting Emma's review before sending.
**Date drafted:** 2026-05-10
**Paper:** *Neural Computers*, Zhuge et al., arxiv 2604.06425
**Senior author:** Jürgen Schmidhuber (KAUST)
**Corresponding author:** Mingchen Zhuge (KAUST)
**Authorship pattern:** 2 × KAUST (Zhuge, Schmidhuber) + 17 × Meta
(Reality Labs / FAIR). The paper's arxiv page does not publish
institutional affiliations or per-author emails; affiliations above
are sourced from each author's public web profile.

---

## Recipient list

### Confirmed addresses (sourced from public profiles)

| Author | Email | Source |
|---|---|---|
| Mingchen Zhuge (corresponding) | `mingchen.zhuge@kaust.edu.sa` *(primary, institutional)* or `mczhuge@gmail.com` | KAUST faculty profile + metauto.ai homepage |
| Jürgen Schmidhuber (senior) | `juergen@idsia.ch` *(long-standing public)* | people.idsia.ch/~juergen/ |
| Vikas Chandra (Senior Director, Meta Reality Labs) | `vchandra@meta.com` | v-chandra.github.io |
| Yuandong Tian | personal: `yuandong.tian@gmail.com` | yuandong-tian.com (note: he has reportedly moved on from Meta as of recent) |

### Not individually sourced — Meta authors

The remaining 15 authors all appear to be at Meta (Reality Labs /
FAIR). Meta's published employee email scheme is
`firstname.lastname@meta.com` (legacy `@fb.com` also routes); I have
NOT verified each address individually against a public profile and
have NOT included guessed emails in this draft — pattern-emailing 15
people on a cold outreach is noisy. The proper protocol is:

1. **Send to Zhuge as corresponding author** — that is the canonical
   channel and is what arxiv's `/show-email/` link is built for.
2. **CC Schmidhuber** as senior author on the same send.
3. **Optionally CC Chandra** as the Meta-side senior, since the
   collaboration question is partly a Meta-AI-resourcing question
   and Chandra is the right person on that side.
4. **Wait for Zhuge to respond** before reaching out to the wider
   author list. If Zhuge says "the right person on this is X," send
   to X. Otherwise don't carpet-bomb 15 inboxes.

Full author list for reference (in arxiv order):
Mingchen Zhuge, Changsheng Zhao, Haozhe Liu, Zijian Zhou, Shuming
Liu, Wenyi Wang, Ernie Chang, Gael Le Lan, Junjie Fei, Wenxuan
Zhang, Yasheng Sun, Zhipeng Cai, Zechun Liu, Yunyang Xiong, Yining
Yang, Yuandong Tian, Yangyang Shi, Vikas Chandra, Jürgen Schmidhuber.

## Subject

A programming language for the Completely Neural Computer — collaboration?

## Body

Dear Dr. Zhuge,

I read *Neural Computers* (arxiv 2604.06425) with real interest. The
framing of the Completely Neural Computer — stable execution, explicit
reprogramming, durable capability reuse on a learned runtime state — is
the same target I have been building toward from the language side,
and I would like to propose we work on the CNC together.

Concretely: I have been developing **Sutra**, a purely functional
programming language whose every operation compiles to substrate tensor
ops on a frozen-LLM semantic subspace. Source compiles to a self-
contained PyTorch program that runs on CPU or CUDA. There is no host-
side numpy on the runtime path, no scalar arithmetic inside an
operation, no libm calls; bundle, bind, unbind, similarity, projection,
rotation, snap, and loop bodies are all tensor expressions on the
embedding substrate. The compiler is the typing surface; the runtime
is uniformly geometric. Repo is at
<https://github.com/EmmaLeonhart/Sutra> and the website at
<https://sutralang.dev>.

The three properties your paper calls out as "remain challenging" —
routine reuse, controlled updates, and symbolic stability — map
directly onto what Sutra's design is built for:

- **Routine reuse** corresponds to function declarations on the
  substrate. Every Sutra function is a fused composition of tensor ops
  that is built once at compile time and applied at the call site; this
  is exactly the "durable capability" your CNC roadmap asks for, and
  it is reusable because it is *symbolic at the language layer* even
  though every step happens on the learned state.
- **Controlled updates** correspond to first-class semantic vs non-
  semantic binding. A learned-matrix bind is a meaningful update on the
  state (e.g. *located-in-country*); an arbitrary-matrix bind is a
  storage operation. The language distinguishes them syntactically, so
  what counts as "reprogramming" the machine is explicit.
- **Symbolic stability** is what Sutra's `is_true` /
  defuzzification machinery is for — sharpening a fuzzy substrate
  state along a target axis while keeping the output differentiable
  and substrate-valued. State stays geometric; the symbolic read is a
  projection, not a commit.

A working **TypeScript → Sutra transpiler** has shipped (14 fixtures,
end-to-end through to runnable Python), which means a real population
of existing programs can already be lowered to run on the substrate.
This is the surface that lets a CNC absorb the world's existing
software corpus instead of being trained on screen-rollout traces.
The video-model instantiation in your paper is one elegant way to
learn the I/O alignment; a transpiler-fed substrate is the
complementary path for the program-rollout side, and the two are
composable rather than competing.

The thing I would like to explore with your group is whether Sutra
could serve as the **substrate programming language for a CNC** — i.e.
the symbolic interface through which a learned runtime is given
durable, reusable, and audit-able routines, while the video-/screen-
rollout side of your work continues to handle the I/O alignment and
short-horizon control you have already shown is learnable. The two
research programmes meet at the same architecture from opposite ends.

A few concrete shapes a collaboration could take, in increasing order
of commitment:

1. A 30-minute call to compare notes on the CNC's symbolic-stability
   gap and where a substrate-tensor-op language fits.
2. A joint short paper / workshop note describing the two-sided
   architecture (Sutra programs on the symbolic side, your video-
   rollout model on the I/O side) with a small joint demo.
3. A deeper integration where Sutra's PyTorch backend becomes one of
   the runtime states that an NC can roll out from, with a shared
   benchmark for routine-reuse durability.

I would be glad to send a longer technical brief, a runnable demo,
or to set up a call at your convenience. Apologies for reaching out
through the arxiv email redirect — feel free to forward this to
whichever of the co-authors are the right readers.

Best,
Emma Leonhart
<immanuelleleonhart@gmail.com>
github.com/EmmaLeonhart/Sutra · sutralang.dev

---

## Notes for Emma before sending

- One concrete demo to attach or link if asked: the TS transpiler
  fixture suite (`sdk/sutra-from-ts/tests/fixtures/`) — 14 small TS
  programs that round-trip through Sutra to runnable Python. Easiest
  proof that the surface story above is not aspirational.
- Schmidhuber is famously protective of priority claims. Nothing in
  the draft asserts that Sutra anticipated *Neural Computers* — the
  framing is "your roadmap and my language target the same thing
  from opposite sides," which is true and avoids that landmine.
- The CNC term and the three "challenging" properties (routine
  reuse / controlled updates / symbolic stability) are pulled
  verbatim from the abstract; that's deliberate — it shows the
  email is responsive to their actual framing, not a generic pitch.
- If the response is curious-but-skeptical, the natural next send
  is a one-page technical brief that walks through one Sutra
  program end-to-end (source → compiled tensor ops → run on
  substrate → decoded output). The existing `examples/` directory
  has candidates.
