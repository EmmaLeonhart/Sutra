"""End-to-end differentiable training through Sutra's tensor-op graph.

Demonstrates that gradient descent can optimize parameters through
the exact operations the Sutra compiler emits to tensor normal form:
cosine similarity, Lagrange-interpolated fuzzy AND/OR/NOT polynomials,
scalar-vector multiply, and bundle (vector addition).

Task: 3-category word classification (animals / vehicles / foods)
using fuzzy if-then rules with learnable prototype embeddings.
Every operation in the forward pass is a Sutra primitive; every
primitive is differentiable.

Architecture:
  input word embedding (frozen, via Ollama)
    -> cosine similarity to each learnable prototype
    -> fuzzy AND/OR/NOT gates (Lagrange polynomials, C^inf)
    -> classification scores
    -> softmax cross-entropy loss
    -> backprop updates prototype embeddings

Called by: standalone experiment for the paper (Section 3.2).

Usage:
    py experiments/differentiable_training.py

Requires: torch, ollama (with nomic-embed-text model pulled)
Outputs:  experiments/differentiable_training_results.json
"""

from __future__ import annotations

import json
import os
import sys
import torch
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Sutra fuzzy-logic primitives — exact match to codegen_pytorch.py
# ---------------------------------------------------------------------------
# These are the Lagrange-interpolated polynomials that the Sutra compiler
# emits for Kleene three-valued logic gates. They are exact on the
# {-1, 0, +1}^2 grid and C^inf everywhere — no branches, no clamps,
# pure polynomial tensor ops.

def fuzzy_and(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Lagrange-interpolated min — exact on {-1, 0, +1}^2.

    Same polynomial as codegen_pytorch.py (lines 963-964):
      min(a, b) = (a + b + ab - a^2 - b^2 + a^2 b^2) / 2
    """
    return (a + b + a * b - a**2 - b**2 + a**2 * b**2) / 2


def fuzzy_or(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Lagrange-interpolated max — exact on {-1, 0, +1}^2.

    Same polynomial as codegen_pytorch.py (lines 965-966):
      max(a, b) = (a + b - ab + a^2 + b^2 - a^2 b^2) / 2
    """
    return (a + b - a * b + a**2 + b**2 - a**2 * b**2) / 2


def fuzzy_not(a: torch.Tensor) -> torch.Tensor:
    """Kleene strong negation: NOT(a) = -a."""
    return -a


# ---------------------------------------------------------------------------
# Embedding helpers — same pipeline as _TorchVSA.embed() / embed_batch()
# ---------------------------------------------------------------------------

def embed_all(
    words: list[str],
    model: str = "nomic-embed-text",
    cache_path: str | None = None,
) -> dict[str, torch.Tensor]:
    """Embed words via Ollama, mean-center, L2-normalize.

    Caches to a .pt file so the experiment can re-run without Ollama.
    Semantic-only vectors (no synthetic block) — the fuzzy logic
    operates on scalar truth values from cosine similarity, not on
    the synthetic axis directly.
    """
    if cache_path and os.path.exists(cache_path):
        cached = torch.load(cache_path, map_location="cpu", weights_only=True)
        # If all words are cached, return them
        if all(w in cached for w in words):
            return cached

    import ollama as _ollama

    r = _ollama.embed(model=model, input=words)
    vecs: dict[str, torch.Tensor] = {}
    for word, emb in zip(words, r["embeddings"]):
        v = torch.tensor(emb, dtype=torch.float32)
        v = v - v.mean()
        n = v.norm()
        if n > 0:
            v = v / n
        vecs[word] = v

    if cache_path:
        torch.save(vecs, cache_path)
    return vecs


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("animal", [
        "dog", "cat", "bird", "fish", "horse", "lion", "tiger", "elephant",
        "rabbit", "monkey", "bear", "wolf", "fox", "deer", "mouse", "snake",
        "frog", "turtle", "dolphin", "whale", "shark", "eagle", "owl",
        "sparrow", "crow", "robin", "parrot", "swan", "duck", "goose",
        "chicken", "cow", "pig", "sheep", "goat", "donkey", "camel",
        "giraffe", "kangaroo", "koala", "panda", "leopard", "cheetah",
        "hippopotamus", "rhinoceros", "antelope", "buffalo", "hedgehog",
        "squirrel", "raccoon",
    ]),
    ("vehicle", [
        "car", "truck", "airplane", "boat", "bicycle", "motorcycle", "bus",
        "train", "ship", "helicopter", "tractor", "scooter", "van", "taxi",
        "jeep", "sailboat", "kayak", "canoe", "raft", "submarine", "glider",
        "jet", "rocket", "spaceship", "sled", "skateboard", "wagon",
        "carriage", "chariot", "ambulance", "firetruck", "limousine",
        "minivan", "hatchback", "sedan", "coupe", "convertible", "pickup",
        "trailer", "ferry", "yacht", "dinghy", "blimp", "balloon",
        "hovercraft", "tram", "moped", "tricycle", "rollerblade", "unicycle",
    ]),
    ("food", [
        "apple", "bread", "cheese", "rice", "pasta", "banana", "salad",
        "soup", "meat", "pizza", "sandwich", "burger", "taco", "sushi",
        "cake", "cookie", "pie", "donut", "muffin", "pancake", "waffle",
        "bagel", "croissant", "omelet", "salmon", "tuna", "beef", "pork",
        "lamb", "bacon", "ham", "sausage", "steak", "lobster", "shrimp",
        "crab", "oyster", "clam", "broccoli", "carrot", "lettuce", "tomato",
        "potato", "cucumber", "onion", "garlic", "pepper", "eggplant",
        "spinach", "mushroom",
    ]),
    ("color", [
        "red", "blue", "green", "yellow", "orange", "purple", "black",
        "white", "brown", "pink", "gray", "cyan", "magenta", "violet",
        "indigo", "turquoise", "teal", "lavender", "maroon", "crimson",
        "scarlet", "ruby", "gold", "silver", "bronze", "copper", "beige",
        "tan", "ivory", "charcoal", "navy", "sapphire", "emerald", "jade",
        "olive", "lime", "mint", "coral", "peach", "plum", "mauve",
        "fuchsia", "amber", "ochre", "sienna", "mahogany", "chocolate",
        "caramel", "mustard", "azure",
    ]),
    ("clothing", [
        "shirt", "pants", "dress", "hat", "shoes", "jacket", "socks",
        "gloves", "scarf", "belt", "sweater", "hoodie", "jeans", "shorts",
        "skirt", "blouse", "coat", "cap", "beanie", "mittens", "tights",
        "leggings", "vest", "blazer", "suit", "tuxedo", "gown", "robe",
        "kimono", "kilt", "poncho", "cloak", "cape", "sneakers", "boots",
        "sandals", "slippers", "heels", "loafers", "tie", "bowtie",
        "cufflinks", "watch", "ring", "necklace", "earrings", "bracelet",
        "anklet", "brooch", "headband",
    ]),
    ("weather", [
        "rain", "snow", "wind", "cloud", "storm", "fog", "frost", "hail",
        "thunder", "lightning", "drizzle", "downpour", "blizzard",
        "hurricane", "tornado", "cyclone", "typhoon", "sleet", "mist",
        "haze", "smog", "sunshine", "sunlight", "sunset", "sunrise", "dawn",
        "dusk", "twilight", "breeze", "gust", "gale", "humidity",
        "drought", "flood", "monsoon", "snowfall", "snowstorm", "rainstorm",
        "sandstorm", "heatwave", "chill", "dew", "hailstorm", "thaw",
        "overcast", "sunny", "cloudy", "rainy", "snowy", "windy",
    ]),
    ("emotion", [
        "joy", "sadness", "anger", "fear", "love", "hope", "surprise",
        "disgust", "pride", "envy", "happiness", "grief", "rage", "anxiety",
        "affection", "despair", "delight", "shame", "guilt", "confidence",
        "contentment", "jealousy", "regret", "sorrow", "frustration",
        "satisfaction", "awe", "wonder", "gratitude", "compassion",
        "sympathy", "empathy", "irritation", "boredom", "excitement",
        "enthusiasm", "calm", "serenity", "melancholy", "nostalgia",
        "longing", "embarrassment", "humiliation", "indifference", "ecstasy",
        "bliss", "dread", "terror", "amusement", "loneliness",
    ]),
    ("tool", [
        "hammer", "saw", "drill", "wrench", "screwdriver", "knife",
        "scissors", "pliers", "axe", "shovel", "rake", "hoe", "spade",
        "pickaxe", "crowbar", "mallet", "chisel", "sander", "level",
        "ruler", "vise", "clamp", "ratchet", "socket", "awl", "scraper",
        "trowel", "broom", "mop", "sponge", "bucket", "ladder",
        "jackhammer", "sledgehammer", "paintbrush", "roller", "stapler",
        "tongs", "tweezers", "calipers", "magnifier", "flashlight",
        "multimeter", "wirecutter", "hacksaw", "router", "torch",
        "soldering_iron", "drillbit", "screwbit",
    ]),
    ("instrument", [
        "guitar", "piano", "drum", "violin", "flute", "trumpet", "saxophone",
        "harp", "cello", "clarinet", "banjo", "mandolin", "ukulele",
        "harmonica", "accordion", "organ", "keyboard", "synthesizer",
        "xylophone", "tambourine", "maracas", "bongos", "marimba",
        "vibraphone", "glockenspiel", "bagpipes", "oboe", "bassoon",
        "trombone", "tuba", "lute", "sitar", "koto", "zither", "dulcimer",
        "cymbal", "gong", "triangle", "cowbell", "snare", "kettledrum",
        "recorder", "piccolo", "fife", "didgeridoo", "theremin", "viola",
        "double_bass", "fiddle", "ocarina",
    ]),
    ("profession", [
        "doctor", "teacher", "lawyer", "engineer", "nurse", "chef",
        "artist", "scientist", "farmer", "plumber", "electrician",
        "carpenter", "mechanic", "pilot", "sailor", "soldier", "judge",
        "journalist", "writer", "poet", "painter", "sculptor", "musician",
        "actor", "dancer", "singer", "photographer", "architect", "dentist",
        "surgeon", "pharmacist", "veterinarian", "librarian", "accountant",
        "banker", "broker", "programmer", "designer", "manager",
        "secretary", "butcher", "baker", "gardener", "tailor", "jeweler",
        "barber", "chemist", "biologist", "physicist", "mathematician",
    ]),
    ("body_part", [
        "head", "hand", "foot", "eye", "ear", "nose", "mouth", "leg", "arm",
        "finger", "toe", "knee", "elbow", "shoulder", "hip", "neck", "back",
        "chest", "stomach", "heart", "brain", "lung", "liver", "kidney",
        "bone", "muscle", "skin", "hair", "throat", "jaw", "chin", "cheek",
        "forehead", "eyebrow", "eyelash", "lip", "tongue", "palm", "wrist",
        "ankle", "thumb", "heel", "spine", "rib", "scalp", "nostril", "gum",
        "knuckle", "tendon", "vein",
    ]),
    ("plant", [
        "tree", "flower", "grass", "bush", "vine", "fern", "moss", "herb",
        "weed", "leaf", "stem", "branch", "bark", "blossom", "petal", "oak",
        "maple", "willow", "birch", "cedar", "bamboo", "cactus", "rose",
        "tulip", "daisy", "lily", "sunflower", "orchid", "ivy", "basil",
        "rosemary", "thyme", "sage", "lavender", "dandelion", "clover",
        "lotus", "magnolia", "sycamore", "redwood", "baobab", "eucalyptus",
        "juniper", "hemlock", "fir", "spruce", "ash", "elm", "poplar",
        "chestnut",
    ]),
    ("furniture", [
        "chair", "table", "sofa", "bed", "desk", "shelf", "drawer",
        "cabinet", "wardrobe", "dresser", "nightstand", "ottoman", "bench",
        "stool", "recliner", "futon", "couch", "armchair", "bookcase",
        "sideboard", "buffet", "cupboard", "hutch", "vanity", "headboard",
        "footboard", "mattress", "pillow", "cushion", "blanket", "quilt",
        "comforter", "lamp", "mirror", "rug", "carpet", "curtain", "blind",
        "shutter", "hammock", "cradle", "crib", "bassinet", "highchair",
        "rocker", "loveseat", "settee", "divan", "chaise", "headrest",
    ]),
    ("building", [
        "house", "apartment", "mansion", "cottage", "cabin", "hut", "igloo",
        "tent", "palace", "castle", "fortress", "tower", "skyscraper",
        "office", "factory", "warehouse", "store", "mall", "restaurant",
        "hotel", "motel", "hospital", "school", "university", "library",
        "museum", "theater", "stadium", "arena", "church", "temple",
        "mosque", "synagogue", "cathedral", "chapel", "monastery", "abbey",
        "barn", "shed", "garage", "basement", "attic", "cellar", "lobby",
        "lounge", "hallway", "corridor", "atrium", "foyer", "balcony",
    ]),
    ("country", [
        "France", "Germany", "Italy", "Spain", "Portugal", "England",
        "Scotland", "Ireland", "Norway", "Sweden", "Finland", "Denmark",
        "Iceland", "Russia", "Poland", "Greece", "Turkey", "Egypt",
        "Morocco", "Algeria", "Kenya", "Nigeria", "Ethiopia", "Ghana",
        "Senegal", "Mali", "Sudan", "Uganda", "Tanzania", "Madagascar",
        "China", "Japan", "Korea", "Vietnam", "Thailand", "Malaysia",
        "Indonesia", "India", "Pakistan", "Bangladesh", "Iran", "Iraq",
        "Israel", "Lebanon", "Australia", "Canada", "Mexico", "Brazil",
        "Argentina", "Chile",
    ]),
    ("sport", [
        "football", "basketball", "baseball", "soccer", "tennis", "golf",
        "hockey", "rugby", "cricket", "volleyball", "swimming", "running",
        "cycling", "skiing", "snowboarding", "surfing", "sailing", "rowing",
        "kayaking", "climbing", "hiking", "boxing", "wrestling", "fencing",
        "archery", "shooting", "fishing", "hunting", "polo", "badminton",
        "ping_pong", "squash", "racquetball", "lacrosse", "handball",
        "dodgeball", "kickball", "gymnastics", "diving", "weightlifting",
        "judo", "karate", "taekwondo", "sumo", "marathon", "triathlon",
        "decathlon", "biathlon", "skating", "bowling",
    ]),
    ("drink", [
        "water", "juice", "milk", "tea", "coffee", "soda", "beer", "wine",
        "whiskey", "vodka", "rum", "gin", "tequila", "brandy", "cognac",
        "champagne", "cocktail", "smoothie", "milkshake", "lemonade",
        "cider", "ale", "lager", "stout", "bourbon", "scotch", "sake",
        "mead", "punch", "eggnog", "kombucha", "kefir", "espresso", "latte",
        "cappuccino", "mocha", "americano", "macchiato", "frappe",
        "hot_chocolate", "cordial", "shake", "slushie", "syrup", "fizz",
        "brew", "tonic", "infusion", "ginger_ale", "root_beer",
    ]),
    ("metal", [
        "gold", "silver", "copper", "iron", "steel", "aluminum", "brass",
        "bronze", "tin", "lead", "zinc", "nickel", "platinum", "titanium",
        "chromium", "mercury", "magnesium", "lithium", "sodium", "potassium",
        "calcium", "uranium", "plutonium", "palladium", "tungsten",
        "vanadium", "cobalt", "manganese", "beryllium", "gallium", "indium",
        "antimony", "bismuth", "cadmium", "cerium", "neodymium", "osmium",
        "rhodium", "ruthenium", "tantalum", "thallium", "thorium", "yttrium",
        "scandium", "hafnium", "niobium", "molybdenum", "rhenium", "iridium",
        "rubidium",
    ]),
    ("shape", [
        "circle", "square", "triangle", "rectangle", "oval", "ellipse",
        "pentagon", "hexagon", "octagon", "diamond", "rhombus", "trapezoid",
        "parallelogram", "polygon", "sphere", "cube", "cylinder", "cone",
        "pyramid", "prism", "cuboid", "tetrahedron", "dodecahedron",
        "icosahedron", "octahedron", "torus", "helix", "spiral", "crescent",
        "star", "heart", "arrow", "cross", "line", "curve", "arc", "ring",
        "loop", "knot", "dot", "vertex", "edge", "angle", "parabola",
        "hyperbola", "sine", "wave", "zigzag", "scallop", "annulus",
    ]),
    ("fabric", [
        "cotton", "wool", "silk", "linen", "polyester", "nylon", "denim",
        "leather", "suede", "velvet", "satin", "lace", "tweed", "cashmere",
        "mohair", "fleece", "fur", "canvas", "burlap", "jute", "flannel",
        "chiffon", "organza", "taffeta", "brocade", "damask", "paisley",
        "gingham", "plaid", "herringbone", "corduroy", "microfiber",
        "spandex", "lycra", "rayon", "viscose", "acrylic", "polypropylene",
        "jersey", "knit", "sherpa", "gabardine", "twill", "muslin", "gauze",
        "mesh", "vinyl", "tulle", "georgette", "voile",
    ]),
]


# ---------------------------------------------------------------------------
# Forward pass — fuzzy rule-based classifier using Sutra operations
# ---------------------------------------------------------------------------

def classify_batch(
    X: torch.Tensor,
    prototypes: list[torch.Tensor],
    temperature: float = 10.0,
) -> torch.Tensor:
    """Classify a batch of input embeddings using fuzzy if-then rules.

    Vectorized version of the per-sample rule:

        sim_i   = cosine(x, prototype_i)
        rule_i  = AND(sim_i, AND_{j != i} NOT(sim_j))

    Each fuzzy gate is a differentiable Lagrange polynomial; the
    AND-of-NOTs is left-folded over the K-1 other classes, so the
    rule for class i is a chain of K-1 nested ANDs.

    X: (N, dim) batch of input vectors.
    prototypes: list of K (dim,) tensors.
    Returns logits (N, K) — fuzzy rule scores * temperature.
    """
    K = len(prototypes)
    P = torch.stack(prototypes, dim=0)                  # (K, dim)
    X_norm = X / (X.norm(dim=1, keepdim=True) + 1e-12)
    P_norm = P / (P.norm(dim=1, keepdim=True) + 1e-12)
    sims = X_norm @ P_norm.T                            # (N, K)

    rules = []
    for i in range(K):
        others = [j for j in range(K) if j != i]
        neg_others = fuzzy_not(sims[:, others[0]])      # (N,)
        for j in others[1:]:
            neg_others = fuzzy_and(neg_others, fuzzy_not(sims[:, j]))
        rule = fuzzy_and(sims[:, i], neg_others)        # (N,)
        rules.append(rule)
    return torch.stack(rules, dim=1) * temperature      # (N, K)


def classify(
    x: torch.Tensor,
    prototypes: list[torch.Tensor],
    temperature: float = 10.0,
) -> torch.Tensor:
    """Single-sample wrapper — returns (K,) logits for one input."""
    return classify_batch(x.unsqueeze(0), prototypes, temperature).squeeze(0)


def evaluate(
    data: list[tuple[torch.Tensor, int]],
    prototypes: list[torch.Tensor],
) -> float:
    """Evaluate classification accuracy (no grad)."""
    correct = 0
    for x, label in data:
        with torch.no_grad():
            logits = classify(x, prototypes)
            if logits.argmax().item() == label:
                correct += 1
    return correct / len(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Sutra: End-to-end differentiable training")
    print("Backpropagation through Lagrange fuzzy-logic gates")
    print("=" * 60)
    print()

    # ---- Step 1: Embed all training words ----
    all_words = [w for _, words in CATEGORIES for w in words]
    cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".diff_train_embeddings.pt",
    )
    print("Step 1: Embedding training data via Ollama (nomic-embed-text)...")
    vecs = embed_all(all_words, cache_path=cache_path)
    dim = next(iter(vecs.values())).shape[0]
    print(f"  {len(vecs)} words embedded, dim={dim}")
    print()

    # ---- Step 2: Build dataset ----
    data: list[tuple[torch.Tensor, int]] = []
    for cat_idx, (_, words) in enumerate(CATEGORIES):
        for w in words:
            data.append((vecs[w], cat_idx))

    # True category centroids (for measuring prototype convergence)
    centroids = []
    for _, words in CATEGORIES:
        c = torch.stack([vecs[w] for w in words]).mean(0)
        c = c / (c.norm() + 1e-12)
        centroids.append(c)

    # ---- Step 3: Initialize learnable prototypes ----
    torch.manual_seed(42)
    prototypes = []
    for _ in range(len(CATEGORIES)):
        p = torch.randn(dim)
        p = p / p.norm()
        p = p.clone().requires_grad_(True)
        prototypes.append(p)

    # ---- Step 4: Evaluate BEFORE training ----
    acc_before = evaluate(data, prototypes)
    cos_before = [
        round(torch.dot(prototypes[i].detach(), centroids[i]).item(), 4)
        for i in range(len(CATEGORIES))
    ]
    print(f"Step 2: Accuracy BEFORE training: {acc_before:.0%} "
          f"(chance = {1/len(CATEGORIES):.0%})")
    print(f"  Proto<->centroid cosine: {cos_before}")
    print()

    # ---- Step 5: Train ----
    optimizer = torch.optim.Adam(prototypes, lr=0.005)
    epochs = 300
    history: list[dict] = []

    print(f"Step 3: Training ({epochs} epochs, Adam lr=0.005)...")
    # Stack the dataset once so each epoch is one batched forward+backward
    # rather than 1000 per-sample SGD steps. The fuzzy-rule pipeline is
    # vectorized across the batch; gradients still reach every prototype
    # and every Lagrange gate, just N at a time.
    X_batch = torch.stack([x for x, _ in data])
    y_batch = torch.tensor([label for _, label in data])

    for epoch in range(epochs):
        optimizer.zero_grad()
        logits = classify_batch(X_batch, prototypes)
        loss = F.cross_entropy(logits, y_batch)
        loss.backward()
        optimizer.step()

        with torch.no_grad():
            preds = logits.argmax(dim=1)
            acc = (preds == y_batch).float().mean().item()
        history.append({
            "epoch": epoch,
            "loss": round(loss.item(), 6),
            "accuracy": round(acc, 4),
        })

        if epoch % 50 == 0 or epoch == epochs - 1:
            cos = [
                f"{torch.dot(prototypes[i].detach(), centroids[i]).item():.3f}"
                for i in range(len(CATEGORIES))
            ]
            print(f"  epoch {epoch:3d}: loss={loss.item():.4f}  "
                  f"acc={acc:.0%}  proto<->centroid={cos}")

    # ---- Step 6: Evaluate AFTER training ----
    acc_after = evaluate(data, prototypes)
    cos_after = [
        round(torch.dot(prototypes[i].detach(), centroids[i]).item(), 4)
        for i in range(len(CATEGORIES))
    ]
    print()
    print(f"Step 4: Accuracy AFTER training: {acc_after:.0%}")
    print(f"  Proto<->centroid cosine: {cos_after}")
    print(f"  Improvement: {acc_before:.0%} -> {acc_after:.0%}")
    print()

    # ---- Step 7: Gradient flow verification ----
    print("Step 5: Gradient flow verification")
    print("  (nonzero gradient => backprop reaches the parameter)")
    grad_norms = {}
    # Cumulative offset of the first word in each category, so the index
    # is correct whether or not all categories have the same word count.
    offset = 0
    for i, (cat_name, words) in enumerate(CATEGORIES):
        optimizer.zero_grad()
        x, label = data[offset]  # first word from this category
        logits = classify(x, prototypes)
        loss = F.cross_entropy(
            logits.unsqueeze(0), torch.tensor([label])
        )
        loss.backward()
        gn = prototypes[i].grad.norm().item()
        grad_norms[cat_name] = round(gn, 8)
        ok = "nonzero" if gn > 0 else "ZERO — gradient blocked!"
        print(f"  d(loss)/d(proto_{cat_name}) norm = {gn:.6f}  ({ok})")
        offset += len(words)

    # ---- Step 8: Save results ----
    results = {
        "experiment": "end-to-end differentiable training through Sutra ops",
        "task": (f"{len(CATEGORIES)}-category word classification "
                 f"({len(data)} words across {len(CATEGORIES)} classes; "
                 f"chance = {1/len(CATEGORIES):.0%})"),
        "sutra_operations_in_forward_pass": [
            "cosine_similarity (torch.dot / norm — Sutra's similarity())",
            "fuzzy_and (Lagrange min polynomial — Sutra's && operator)",
            "fuzzy_not (Kleene negation — Sutra's ! operator)",
            "scalar * temperature (element-wise — Sutra's scalar multiply)",
            "cross_entropy (softmax + NLL over fuzzy rule scores)",
        ],
        "embedding_model": "nomic-embed-text",
        "embedding_dim": dim,
        "training_words": len(data),
        "categories": [name for name, _ in CATEGORIES],
        "epochs": epochs,
        "accuracy_before": acc_before,
        "accuracy_after": acc_after,
        "proto_centroid_cosine_before": {
            name: cos_before[i]
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "proto_centroid_cosine_after": {
            name: cos_after[i]
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "gradient_norms": grad_norms,
        "history": history,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "differentiable_training_results.json",
    )
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print()
    print(f"Results saved to {out_path}")

    # Save trained weights (prototype tensors + input embeddings)
    weights_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "differentiable_training_weights.pt",
    )
    torch.save({
        "prototypes": {
            name: prototypes[i].detach().cpu()
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "centroids": {
            name: centroids[i].cpu()
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "embeddings": {k: v.cpu() for k, v in vecs.items()},
    }, weights_path)
    print(f"Trained weights saved to {weights_path}")

    # ---- Assertions for SKILL.md reproduction ----
    assert acc_after > acc_before, (
        f"Training did not improve accuracy: {acc_before} -> {acc_after}"
    )
    assert all(g > 0 for g in grad_norms.values()), (
        f"Gradient blocked for some prototypes: {grad_norms}"
    )
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
