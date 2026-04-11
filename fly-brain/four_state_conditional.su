// Four-state conditional on Drosophila connectome
// Substrate: mushroom body olfactory circuit (50 PNs → 2000 KCs → APL → 20 MBONs)
//
// Two fuzzy axes:
//   Axis 1: olfactory input (smell present or absent)
//   Axis 2: internal state (hungry or fed)
//
// Four behavioral outputs:
//   smell + hungry  → approach  (go eat)
//   smell + fed     → ignore   (not interested)
//   no smell + hungry → search  (look for food)
//   no smell + fed    → idle   (do nothing)
//
// The if-statements are NOT boolean logic. Each axis is a fuzzy value
// computed by the mushroom body's sparse random projection + winner-take-all
// cleanup. defuzzy() collapses the continuous similarity score to a discrete
// branch. The fly brain does the computation; the if-statement just reads
// the result.

function vector SmellInput() {
    return embed("vinegar");       // or embed("clean_air") for no-smell case
}

function vector HungerState() {
    return embed("hungry");        // or embed("fed") for satiated case
}

// --- Main program ---

// Embed inputs
vector smell = SmellInput();
vector hunger = HungerState();

// Process through mushroom body circuit.
// snap() encodes as PN currents, runs the spiking simulation
// (APL enforces 5% KC sparsity), decodes from KC population.
vector smell_clean = snap(smell);
vector hunger_clean = snap(hunger);

// Fuzzy comparison against reference concepts.
// These are cosine similarities in the fly brain's sparse coding space.
fuzzy has_smell = similarity(smell_clean, embed("vinegar"));
fuzzy is_hungry = similarity(hunger_clean, embed("hungry"));

// Defuzzify and branch — four behavioral states
if (defuzzy(has_smell)) {
    if (defuzzy(is_hungry)) {
        return "approach";
    } else {
        return "ignore";
    }
} else {
    if (defuzzy(is_hungry)) {
        return "search";
    } else {
        return "idle";
    }
}
