# Equality matrices (is_cat, is_true, is_false) and conditional ops

_Excerpt from the original `chats/vsa-programming-languages.md` (lines 691-782). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

I’m not sure. I don’t know the degree we need a massive amount but we at least need permutation operations which would use identity to returnOkay. So what I have right now is basically, I have, like, way too, like, essentially equality thing of, like, does one does one vector equal another thing? Does one vector equal another thing? So for example, does a, There's a count vector, and then there's a does the cat equal, whatever. There's there's a compactor and there's, like, a does the count equal, There's a cat vector, and the cat vector is like does the chat equal There's a cat vector, and then there is a, a Matrix post multiply vibe that is, the IS cat vector and it returns true or false depending on what the same word count or not. This is like an equality an equality, operation, basically. And With service in mind, Let's assume that I've got this sorted out. I have this implemented. I'll And it returns false if it if it is false. False. In relatively empty spaces. What does it mean as far as, number of vectors in relatively empty spaces? Well, the number of vectors have relatively empty spaces. All this being said, it basically means that, All of this being, the best thing is that, like, All of this being Sarajev is gonna be his step. But this this this alone wouldn't really be sufficient for, like, long would it really be sufficient for, like, We're, like, establishing like Washington. Logical operations like a NAND or an AND or a core. I'm not sure what would be because I don't think that's that's much more that would be needed. I guess we need, like, maybe, I think we've all resolved this because there's an is an there is a use to So there's a is cat. Vector There's also added is true vector. Sorry. An issue through Matrix. So if there's an East Through Matrix Then there would also be, like, an is false matrix. The is false matrix turns it just inverts it. I'm just thinking if this is there enough coverage? From there, there's probably going to be enough For them, we're just thinking, like, there's I feel like this is not quite enough, but we're almost there.


**Claude:**

I can follow the thread here -- you're essentially working out the **primitive operation set**. Let me reflect back what I think you're describing and we can check if it's right:

**What you have so far:**

- A **cat vector** -- atomic symbol representation

- A **count vector** -- some kind of numeric/quantity representation

- An **IS_cat matrix** -- post-multiply a vector, returns something in true/false space

- An **IS_true matrix** -- maps to true

- An **IS_false matrix** -- inverts, maps to false

- **Equality operation** -- does vector A match vector B, returns true/false via similarity

**What you're sensing is missing**

You're right that equality + true/false alone isn't sufficient for general logical operations. You'd need at minimum:

- **AND** -- both things are true

- **OR** -- at least one is true

- **NOT** -- inversion (your IS_false matrix might cover this)

- **NAND** -- which gives you everything else if needed

**The good news**

In VSA these can potentially all be expressed as matrix operations or binding compositions rather than separate primitives. NOT you arguably already have. AND might be expressible as binding. OR might be bundling.

**The thing I think is actually missing**

Conditional execution -- **if this is true, do X, otherwise do Y**. That's the bridge from logical operations to actual computation.

Does that feel like the gap you're sensing?


**Human:**

I think I can I think I can actually do conditional operation? Like, I'm just I'm pretty convinced that I can do conditional operation.Although it's not although I will say it's not White is easy as the other ones. I think it's possible because, I think that the I think that, like, deriving true true and false, and then doing some other, like, stuff was the main real limitation What's the name of your And conditional operation is Comparatively, Unconditional operation is like not sure the degree it could be decomposed into like, I'm not I'm not sure if it at the degree it would be able to be decomposed into linear. The decompose into coset time. But I think you could do something Then I can get That's kind of the big thing.


**Claude:**

Yeah I think you're right that conditional is achievable but it's the hardest primitive because:

**Why equality/true/false was the real blocker**

Once you have a reliable true/false representation in the embedding space, conditional becomes a routing problem rather than a logic problem. You already have the hard part.

**Why conditional is harder to decompose linearly**

You're sensing something real there. Conditionals are inherently **nonlinear** -- the output depends on which branch you take, which depends on the input. In VSA terms:

- Linear operations (matrix multiply) are smooth and continuous

- Branching is discontinuous -- you go one way or the other

- That discontinuity is hard to express as a single matrix operation

**But there's a VSA-natural way to do it**

Something like:

`result = (condition * branch_true) + (NOT condition * branch_false)`

Where:

- `*` is binding

- `+` is bundling

- You extract the relevant branch via unbinding after

The condition vector essentially **gates** which branch dominates in the output. It's not clean binary branching but it's statistically reliable if your true/false representation is well separated in the embedding space.

**Which connects back to your empty latent space point**

The cleaner your true/false vectors are separated in embedding space, the more reliable your conditionals are. That separation is probably something the initiation phase needs to explicitly optimize for.

Does that decomposition feel like what you were intuiting?


