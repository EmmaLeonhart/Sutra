"""
Structured Matching Primitive — Full Implementation
====================================================

Implements the three-part query:
  1. Active selection  — maximize similarity along a target direction
  2. Active control    — orthogonally project away confounding dimensions
  3. Residual similarity — cosine on the residual, uncorrelated with controlled dims

This is the core algorithm of the paper. Previous script (dimensional_decomposition.py)
only implemented parts 2 and 3 on toy data. This script implements all three parts
and runs on larger, real-world-scale datasets.

Usage:
    python scripts/structured_matching.py
    python scripts/structured_matching.py --model mxbai-embed-large
    python scripts/structured_matching.py --all-models
    python scripts/structured_matching.py --n-candidates 100
"""

import argparse
import json
import os
import sys
import time
import io

import numpy as np
from scipy.spatial.distance import cosine as cosine_dist

# Windows Unicode fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ============================================================
# Embedding backend
# ============================================================

def embed_ollama(texts, model="mxbai-embed-large"):
    """Embed texts via Ollama API."""
    import ollama
    result = ollama.embed(model=model, input=texts)
    return np.array(result.embeddings)


def get_embedder(model_name):
    """Return (embed_fn, display_name) for a given model name."""
    return lambda texts: embed_ollama(texts, model=model_name), f"Ollama/{model_name}"


# ============================================================
# Core Algorithm: The Three-Part Structured Matching Primitive
# ============================================================

def compute_direction(embeddings_group_a, embeddings_group_b):
    """
    Derive a unit direction vector as the mean displacement between two groups.
    Used for both control vectors and selection vectors.
    """
    mean_a = np.mean(embeddings_group_a, axis=0)
    mean_b = np.mean(embeddings_group_b, axis=0)
    direction = mean_a - mean_b
    norm = np.linalg.norm(direction)
    if norm < 1e-10:
        return direction
    return direction / norm


def project_away(embeddings, control_vectors):
    """
    Remove components along all control vectors from each embedding.
    Supports multiple control dimensions.

    Args:
        embeddings: (N, d) array or (d,) vector
        control_vectors: list of (d,) unit vectors to project away

    Returns:
        Residual embeddings with all control dimensions removed.
    """
    single = embeddings.ndim == 1
    if single:
        embeddings = embeddings.reshape(1, -1)

    result = embeddings.copy()
    for v in control_vectors:
        vv = np.dot(v, v)
        if vv < 1e-10:
            continue
        projections = (result @ v) / vv
        result = result - np.outer(projections, v)

    return result[0] if single else result


def structured_match(query, candidates, target_direction, control_vectors,
                     alpha=0.5, beta=0.5):
    """
    The three-part structured matching primitive.

    Given a query and candidates, compute a matching score that:
      1. SELECTS for similarity along target_direction (directional traversal)
      2. CONTROLS by projecting away control dimensions (confounders removed)
      3. Measures RESIDUAL similarity on what's left (general similarity)

    Score = alpha * cos(q_residual, c_residual) + beta * proj_target(c)

    Args:
        query: (d,) query embedding
        candidates: (N, d) candidate embeddings
        target_direction: (d,) unit vector — dimension to select FOR
        control_vectors: list of (d,) unit vectors — dimensions to exclude
        alpha: weight on residual similarity (part 3)
        beta: weight on target selection (part 1)

    Returns:
        scores: (N,) array of structured matching scores
    """
    # Part 2: Project away control dimensions from query and all candidates
    q_residual = project_away(query, control_vectors)
    c_residuals = project_away(candidates, control_vectors)

    # Part 3: Residual cosine similarity
    q_norm = np.linalg.norm(q_residual)
    if q_norm < 1e-10:
        residual_scores = np.zeros(len(candidates))
    else:
        q_unit = q_residual / q_norm
        c_norms = np.linalg.norm(c_residuals, axis=1, keepdims=True)
        c_norms = np.maximum(c_norms, 1e-10)
        c_units = c_residuals / c_norms
        residual_scores = c_units @ q_unit

    # Part 1: Directional selection — project candidates onto target direction
    selection_scores = candidates @ target_direction  # raw projection
    # Normalize to [0, 1] range for composability
    sel_min = selection_scores.min()
    sel_max = selection_scores.max()
    if sel_max - sel_min > 1e-10:
        selection_scores = (selection_scores - sel_min) / (sel_max - sel_min)
    else:
        selection_scores = np.ones(len(candidates)) * 0.5

    # Composite score
    scores = alpha * residual_scores + beta * selection_scores
    return scores


def naive_cosine_ranking(query, candidates):
    """Baseline: rank candidates by naive cosine similarity."""
    q_norm = np.linalg.norm(query)
    if q_norm < 1e-10:
        return np.zeros(len(candidates))
    q_unit = query / q_norm
    c_norms = np.linalg.norm(candidates, axis=1, keepdims=True)
    c_norms = np.maximum(c_norms, 1e-10)
    c_units = candidates / c_norms
    return c_units @ q_unit


# ============================================================
# Large-scale datasets with real entities
# ============================================================

def get_countries_dataset():
    """
    Countries dataset: find countries similar in GOVERNANCE SYSTEM
    while controlling for GEOGRAPHIC REGION.

    50+ countries, real entities, meaningful confounders.
    """
    # Target: governance type (what we want to match on)
    governance_exemplars_democratic = [
        "parliamentary democracy with constitutional monarchy",
        "federal republic with separation of powers",
        "representative democracy with free elections",
        "liberal democracy with independent judiciary",
        "constitutional government with rule of law",
    ]
    governance_exemplars_authoritarian = [
        "single-party state with centralized power",
        "authoritarian government with state control",
        "military junta with martial law",
        "dictatorship with no free elections",
        "totalitarian regime with censorship",
    ]

    # Confounder: geographic region (what we want to control for)
    region_europe = [
        "European country in Western Europe with EU membership",
        "Nordic country in Scandinavia with cold climate",
        "Mediterranean country in Southern Europe with warm climate",
        "Eastern European country with post-Soviet history",
        "Central European country in the heart of Europe",
    ]
    region_asia = [
        "Asian country in East Asia with monsoon climate",
        "Southeast Asian country with tropical climate",
        "Central Asian country with steppe landscape",
        "South Asian country in the Indian subcontinent",
        "Middle Eastern country in Western Asia",
    ]

    # Query: a European democracy
    query = "United Kingdom: parliamentary democracy, constitutional monarchy, Western Europe, island nation"

    # Candidates: mix of democracies and non-democracies across regions
    # Format: (description, is_democratic, region)
    candidates = [
        # European democracies (correct: match governance, match region)
        ("Germany: federal parliamentary republic, Western Europe, EU member state", True, "europe"),
        ("France: semi-presidential republic, Western Europe, EU founding member", True, "europe"),
        ("Sweden: parliamentary constitutional monarchy, Scandinavia, Nordic country", True, "europe"),
        ("Netherlands: parliamentary constitutional monarchy, Western Europe, EU member", True, "europe"),
        ("Denmark: parliamentary constitutional monarchy, Scandinavia, Nordic welfare state", True, "europe"),
        ("Norway: parliamentary constitutional monarchy, Scandinavia, high income", True, "europe"),
        ("Belgium: federal parliamentary constitutional monarchy, Western Europe", True, "europe"),
        ("Ireland: parliamentary republic, Western Europe, island nation", True, "europe"),
        ("Finland: parliamentary republic, Nordic country, EU member", True, "europe"),
        ("Austria: federal parliamentary republic, Central Europe, EU member", True, "europe"),

        # Asian democracies (correct: match governance, wrong region)
        ("Japan: parliamentary constitutional monarchy, East Asia, island nation", True, "asia"),
        ("South Korea: presidential republic, East Asia, democratic since 1987", True, "asia"),
        ("India: federal parliamentary republic, South Asia, largest democracy", True, "asia"),
        ("Taiwan: semi-presidential republic, East Asia, vibrant democracy", True, "asia"),
        ("Indonesia: presidential republic, Southeast Asia, largest Muslim democracy", True, "asia"),

        # African democracies (correct: match governance, different region)
        ("Botswana: parliamentary republic, Southern Africa, stable democracy since independence", True, "africa"),
        ("Ghana: presidential republic, West Africa, democratic since 1992", True, "africa"),
        ("Senegal: presidential republic, West Africa, democratic tradition", True, "africa"),
        ("South Africa: parliamentary republic, Southern Africa, democracy since 1994", True, "africa"),
        ("Mauritius: parliamentary republic, Indian Ocean island, stable democracy", True, "africa"),

        # European non-democracies (wrong: wrong governance, match region)
        ("Belarus: presidential republic in name, authoritarian in practice, Eastern Europe", False, "europe"),
        ("Russia: federal semi-presidential republic, authoritarian, Eastern Europe and Northern Asia", False, "europe"),
        ("Hungary: parliamentary republic, democratic backsliding, Central Europe, EU member", False, "europe"),
        ("Turkey: presidential republic, increasingly authoritarian, transcontinental Europe-Asia", False, "europe"),

        # Asian non-democracies (wrong: wrong governance, wrong region)
        ("China: one-party socialist republic, East Asia, CPC rule since 1949", False, "asia"),
        ("North Korea: one-party state, East Asia, totalitarian regime", False, "asia"),
        ("Vietnam: one-party socialist republic, Southeast Asia, communist party rule", False, "asia"),
        ("Saudi Arabia: absolute monarchy, Middle East, no elections", False, "asia"),
        ("Iran: theocratic republic, Middle East, supreme leader system", False, "asia"),
        ("Myanmar: military junta, Southeast Asia, coup in 2021", False, "asia"),
        ("Laos: one-party socialist republic, Southeast Asia, communist rule", False, "asia"),
        ("Turkmenistan: presidential republic, Central Asia, authoritarian", False, "asia"),

        # African non-democracies (wrong: wrong governance, different region)
        ("Eritrea: one-party state, East Africa, no elections since independence", False, "africa"),
        ("Equatorial Guinea: presidential republic, Central Africa, authoritarian since 1979", False, "africa"),
        ("Chad: presidential republic, Central Africa, military rule", False, "africa"),

        # Latin American democracies (correct governance, different region)
        ("Costa Rica: presidential republic, Central America, no military since 1948", True, "latam"),
        ("Uruguay: presidential republic, South America, strong democratic tradition", True, "latam"),
        ("Chile: presidential republic, South America, democratic since 1990", True, "latam"),

        # Latin American non-democracies
        ("Cuba: one-party socialist republic, Caribbean, communist rule since 1959", False, "latam"),
        ("Venezuela: presidential republic, South America, authoritarian since 2000s", False, "latam"),
        ("Nicaragua: presidential republic, Central America, authoritarian backsliding", False, "latam"),
    ]

    return {
        "name": "Countries: Governance System vs. Geographic Region",
        "description": (
            "Match countries by governance type (democracy vs authoritarian) "
            "while controlling for geographic region. 40 countries across 4 regions."
        ),
        "target_exemplars_positive": governance_exemplars_democratic,
        "target_exemplars_negative": governance_exemplars_authoritarian,
        "confounder_group_a": region_europe,
        "confounder_group_b": region_asia,
        "query": query,
        "candidates": candidates,
        "correct_fn": lambda c: c[1],  # is_democratic
        "label_fn": lambda c: c[0][:60],
    }


def get_occupations_dataset():
    """
    Occupations dataset: find occupations similar in SKILL REQUIREMENTS
    while controlling for SOCIAL PRESTIGE.

    40+ occupations, testing whether we can match by actual skills
    when prestige language dominates descriptions.
    """
    prestige_high = [
        "prestigious elite profession highly respected in society with high income",
        "top-tier career requiring advanced degrees from leading universities",
        "executive leadership role commanding authority and respect",
        "distinguished professional recognized by peers and society",
        "upper-class occupation associated with wealth and social standing",
    ]
    prestige_low = [
        "working-class manual labor job with modest pay",
        "blue-collar trade requiring physical work and apprenticeship",
        "service industry position with low social prestige",
        "entry-level job requiring no formal education",
        "unglamorous but necessary work done by everyday people",
    ]

    # Skills we want to match on
    analytical_skill = [
        "occupation requiring strong analytical and quantitative reasoning",
        "career involving data analysis statistics and mathematical modeling",
        "profession requiring logical problem solving and critical thinking",
        "role involving systematic investigation and evidence-based conclusions",
        "work centered on pattern recognition and complex system analysis",
    ]
    caring_skill = [
        "occupation requiring empathy compassion and interpersonal skills",
        "career involving direct care and emotional support for people",
        "profession requiring patience listening and human connection",
        "role involving nurturing teaching and helping others develop",
        "work centered on healing comfort and human wellbeing",
    ]

    query = "data scientist: analyzes large datasets using statistics and machine learning, builds predictive models, requires quantitative skills, works in technology companies"

    candidates = [
        # Analytical + high prestige (correct skill, prestige-matched to typical framing)
        ("surgeon: performs complex medical procedures requiring precision analysis and decision-making under pressure, highly prestigious", True, "high"),
        ("investment banker: analyzes financial markets builds valuation models requires quantitative skills, elite profession", True, "high"),
        ("physicist: investigates fundamental laws of nature using mathematical models and experiments, prestigious academic career", True, "high"),
        ("management consultant: analyzes business problems with data-driven frameworks, prestigious firm partnerships", True, "high"),
        ("aerospace engineer: designs aircraft using computational modeling and structural analysis, respected technical profession", True, "high"),

        # Analytical + low prestige (correct skill, prestige-mismatched)
        ("auto mechanic: diagnoses complex mechanical and electrical systems through systematic troubleshooting, blue-collar trade", True, "low"),
        ("bookkeeper: tracks financial transactions and reconciles accounts using spreadsheets, modest office work", True, "low"),
        ("quality control inspector: analyzes product defects using statistical sampling and measurement tools, factory floor work", True, "low"),
        ("IT helpdesk technician: diagnoses computer problems through systematic debugging, entry-level tech support", True, "low"),
        ("insurance claims adjuster: analyzes documentation and evidence to assess claim validity, mid-level office work", True, "low"),
        ("land surveyor: uses trigonometry and measurement instruments to map terrain precisely, outdoor fieldwork", True, "low"),
        ("lab technician: runs analytical tests follows protocols records quantitative data, routine laboratory work", True, "low"),

        # Caring + high prestige (wrong skill, prestige-matched)
        ("psychiatrist: provides emotional support and therapy to patients with mental health conditions, medical doctor", False, "high"),
        ("university professor of social work: teaches and mentors students in human services, tenured academic position", False, "high"),
        ("pediatrician: cares for children's health and development with compassion and patience, respected medical specialty", False, "high"),
        ("clinical psychologist: provides therapy and emotional support using evidence-based counseling, doctoral-level profession", False, "high"),

        # Caring + low prestige (wrong skill, prestige-mismatched)
        ("home health aide: provides daily personal care and companionship to elderly patients, low-wage care work", False, "low"),
        ("daycare worker: nurtures and supervises young children with patience and warmth, modest childcare wage", False, "low"),
        ("nursing assistant: helps patients with basic needs like bathing and feeding in hospitals, entry-level healthcare", False, "low"),
        ("school bus driver: ensures safe transport of children, requires patience and care, service industry", False, "low"),
        ("hospice volunteer: provides comfort and companionship to terminally ill patients, unpaid care work", False, "low"),
        ("animal shelter worker: cares for abandoned animals with compassion, physically demanding low-wage work", False, "low"),
        ("social worker: helps vulnerable populations navigate systems with empathy, modest government salary", False, "low"),
        ("eldercare companion: provides emotional support and daily assistance to seniors, informal care work", False, "low"),

        # Mixed/ambiguous
        ("nurse practitioner: combines analytical clinical skills with compassionate patient care, mid-level medical profession", True, "high"),
        ("veterinarian: diagnoses animal diseases analytically while caring compassionately for animals, respected profession", True, "high"),
        ("forensic accountant: investigates financial fraud through detailed analytical examination of records, specialized niche", True, "low"),
        ("plumber: diagnoses water system problems through systematic analysis of pipe networks, blue-collar trade", True, "low"),
        ("electrician: analyzes electrical systems and circuits through systematic troubleshooting, skilled trade", True, "low"),
    ]

    return {
        "name": "Occupations: Analytical Skill vs. Social Prestige",
        "description": (
            "Match occupations by analytical skill requirements while controlling "
            "for social prestige framing. 29 occupations across skill/prestige axes."
        ),
        "target_exemplars_positive": analytical_skill,
        "target_exemplars_negative": caring_skill,
        "confounder_group_a": prestige_high,
        "confounder_group_b": prestige_low,
        "query": query,
        "candidates": candidates,
        "correct_fn": lambda c: c[1],
        "label_fn": lambda c: c[0][:60],
    }


def get_animals_dataset():
    """
    Animals dataset: find animals similar in HABITAT/ECOLOGY
    while controlling for PHYLOGENETIC CLASS.

    Tests whether we can match ecological niche when taxonomy dominates.
    """
    class_mammal = [
        "warm-blooded mammal with fur or hair that nurses its young with milk",
        "placental mammal vertebrate with four-chambered heart",
        "mammalian species with live birth and parental care",
        "furry four-legged animal belonging to class Mammalia",
        "endothermic vertebrate of the mammal class",
    ]
    class_fish = [
        "cold-blooded fish with gills and scales living underwater",
        "aquatic vertebrate with fins that breathes through gills",
        "fish species of class Actinopterygii or Chondrichthyes",
        "marine or freshwater fish with streamlined body",
        "gill-breathing aquatic animal of the fish class",
    ]

    habitat_aquatic = [
        "animal living in water habitats like oceans rivers and lakes",
        "aquatic organism adapted to swimming and underwater life",
        "species found in marine coastal or freshwater environments",
        "water-dwelling creature with adaptations for aquatic life",
        "organism whose primary habitat is aquatic environments",
    ]
    habitat_terrestrial = [
        "land-dwelling animal living on solid ground",
        "terrestrial organism adapted to walking or running on land",
        "species found in forests grasslands deserts or mountains",
        "ground-based creature with legs for terrestrial locomotion",
        "organism whose primary habitat is land environments",
    ]

    query = "dolphin: aquatic mammal living in oceans, highly intelligent, breathes air but lives entirely in water, social pods"

    candidates = [
        # Aquatic mammals (correct habitat, confounding class match with query)
        ("whale: massive aquatic mammal living in oceans worldwide, breathes air at surface", True, "mammal"),
        ("seal: semi-aquatic mammal found in coastal waters, hunts fish underwater", True, "mammal"),
        ("manatee: large aquatic mammal living in warm coastal waters and rivers, herbivore", True, "mammal"),
        ("otter: semi-aquatic mammal living in rivers and coastal waters, uses tools", True, "mammal"),
        ("walrus: large aquatic mammal in Arctic waters, tusks for ice navigation", True, "mammal"),
        ("narwhal: Arctic aquatic mammal with long spiral tusk, lives under sea ice", True, "mammal"),
        ("dugong: aquatic mammal in warm Indo-Pacific waters, seagrass grazer", True, "mammal"),

        # Aquatic fish (correct habitat, different class)
        ("tuna: fast-swimming fish in open oceans, streamlined body for speed", True, "fish"),
        ("salmon: fish that lives in ocean then returns to freshwater rivers to spawn", True, "fish"),
        ("clownfish: small coral reef fish living in tropical ocean waters with anemones", True, "fish"),
        ("great white shark: large predatory fish in temperate and tropical oceans", True, "fish"),
        ("manta ray: large flat fish gliding through tropical ocean waters, filter feeder", True, "fish"),
        ("seahorse: small fish in shallow tropical waters, unique upright posture", True, "fish"),
        ("anglerfish: deep-sea fish with bioluminescent lure, lives in ocean depths", True, "fish"),
        ("swordfish: large ocean fish with elongated bill, fast swimmer in open seas", True, "fish"),

        # Terrestrial mammals (wrong habitat, class match with query)
        ("wolf: terrestrial mammal hunting in packs across forests and tundra", False, "mammal"),
        ("elephant: large terrestrial mammal in African and Asian grasslands and forests", False, "mammal"),
        ("lion: terrestrial mammal predator in African savannas, social prides", False, "mammal"),
        ("bear: large terrestrial mammal in forests and mountains, omnivore", False, "mammal"),
        ("deer: terrestrial mammal in forests and meadows, herbivore with antlers", False, "mammal"),
        ("horse: terrestrial mammal domesticated for riding, lives on grasslands", False, "mammal"),
        ("rabbit: small terrestrial mammal in meadows and burrows, herbivore", False, "mammal"),
        ("bat: flying mammal active at night, roosts in caves and trees on land", False, "mammal"),
        ("giraffe: tall terrestrial mammal browsing treetops in African savanna", False, "mammal"),
        ("kangaroo: terrestrial mammal hopping across Australian grasslands", False, "mammal"),
        ("cheetah: fastest terrestrial mammal sprinting across African plains", False, "mammal"),
        ("gorilla: terrestrial primate in African tropical forests", False, "mammal"),

        # Terrestrial non-mammals (wrong habitat, different class — distant)
        ("eagle: terrestrial bird of prey soaring over mountains and forests", False, "bird"),
        ("rattlesnake: terrestrial reptile in dry desert and grassland habitats", False, "reptile"),
        ("tortoise: slow terrestrial reptile in dry grasslands and deserts", False, "reptile"),
    ]

    return {
        "name": "Animals: Aquatic Habitat vs. Phylogenetic Class",
        "description": (
            "Match animals by habitat (aquatic) while controlling for phylogenetic class "
            "(mammal vs. fish). 30 animals testing ecological vs. taxonomic matching."
        ),
        "target_exemplars_positive": habitat_aquatic,
        "target_exemplars_negative": habitat_terrestrial,
        "confounder_group_a": class_mammal,
        "confounder_group_b": class_fish,
        "query": query,
        "candidates": candidates,
        "correct_fn": lambda c: c[1],
        "label_fn": lambda c: c[0][:60],
    }


# ============================================================
# Run experiment
# ============================================================

def run_experiment(dataset, embed_fn, model_name):
    """Run structured matching experiment with all three parts."""
    print(f"\n{'='*70}")
    print(f"  {dataset['name']}")
    print(f"  Model: {model_name}")
    print(f"{'='*70}")
    print(f"  {dataset['description']}")

    candidates = dataset["candidates"]
    n_candidates = len(candidates)
    n_correct = sum(1 for c in candidates if dataset["correct_fn"](c))
    print(f"  {n_candidates} candidates, {n_correct} correct\n")

    # Collect all texts
    all_texts = []
    all_texts.extend(dataset["target_exemplars_positive"])
    all_texts.extend(dataset["target_exemplars_negative"])
    all_texts.extend(dataset["confounder_group_a"])
    all_texts.extend(dataset["confounder_group_b"])
    all_texts.append(dataset["query"])
    candidate_texts = [dataset["label_fn"](c) for c in candidates]
    all_texts.extend(candidate_texts)

    print(f"  Embedding {len(all_texts)} texts...")
    t0 = time.time()
    all_embeddings = embed_fn(all_texts)
    dim = all_embeddings.shape[1]
    t1 = time.time()
    print(f"  Done in {t1-t0:.1f}s ({dim}-dim)\n")

    # Unpack
    idx = 0
    n_tp = len(dataset["target_exemplars_positive"])
    n_tn = len(dataset["target_exemplars_negative"])
    n_ca = len(dataset["confounder_group_a"])
    n_cb = len(dataset["confounder_group_b"])

    target_pos_emb = all_embeddings[idx:idx+n_tp]; idx += n_tp
    target_neg_emb = all_embeddings[idx:idx+n_tn]; idx += n_tn
    conf_a_emb = all_embeddings[idx:idx+n_ca]; idx += n_ca
    conf_b_emb = all_embeddings[idx:idx+n_cb]; idx += n_cb
    query_emb = all_embeddings[idx]; idx += 1
    cand_embs = all_embeddings[idx:]

    # Derive vectors
    target_direction = compute_direction(target_pos_emb, target_neg_emb)
    control_vector = compute_direction(conf_a_emb, conf_b_emb)

    # Verify orthogonality between target and control
    target_control_dot = abs(np.dot(target_direction, control_vector))
    print(f"  Target-control alignment: {target_control_dot:.4f} (0 = fully independent)")

    correct_mask = np.array([dataset["correct_fn"](c) for c in candidates])

    # --- Method 1: Naive cosine ---
    naive_scores = naive_cosine_ranking(query_emb, cand_embs)
    naive_ranking = np.argsort(-naive_scores)
    naive_ranks = np.where(correct_mask[naive_ranking])[0] + 1  # 1-indexed

    # --- Method 2: Control only (project away confounder, no selection) ---
    q_ctrl = project_away(query_emb, [control_vector])
    c_ctrl = project_away(cand_embs, [control_vector])
    ctrl_scores = naive_cosine_ranking(q_ctrl, c_ctrl)
    ctrl_ranking = np.argsort(-ctrl_scores)
    ctrl_ranks = np.where(correct_mask[ctrl_ranking])[0] + 1

    # --- Method 3: Full three-part structured matching ---
    struct_scores = structured_match(
        query_emb, cand_embs, target_direction, [control_vector],
        alpha=0.5, beta=0.5
    )
    struct_ranking = np.argsort(-struct_scores)
    struct_ranks = np.where(correct_mask[struct_ranking])[0] + 1

    # Metrics
    def compute_metrics(ranks, n_correct, n_total):
        mrr = np.mean(1.0 / ranks) if len(ranks) > 0 else 0
        prec_at_k = sum(1 for r in ranks if r <= n_correct) / n_correct if n_correct > 0 else 0
        mean_rank = np.mean(ranks) if len(ranks) > 0 else n_total
        # NDCG@k where k = n_correct
        dcg = sum(1.0 / np.log2(r + 1) for r in ranks if r <= n_correct * 2)
        ideal_dcg = sum(1.0 / np.log2(i + 1) for i in range(1, n_correct + 1))
        ndcg = dcg / ideal_dcg if ideal_dcg > 0 else 0
        return {
            "mrr": mrr,
            f"precision_at_{n_correct}": prec_at_k,
            "mean_rank": mean_rank,
            "ndcg": ndcg,
        }

    naive_metrics = compute_metrics(naive_ranks, n_correct, n_candidates)
    ctrl_metrics = compute_metrics(ctrl_ranks, n_correct, n_candidates)
    struct_metrics = compute_metrics(struct_ranks, n_correct, n_candidates)

    # Print results
    print(f"\n  {'Method':<30} {'MRR':>8} {'P@{0}'.format(n_correct):>8} {'MeanRank':>10} {'NDCG':>8}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")
    for name, m in [("Naive cosine", naive_metrics),
                     ("Control only (part 2+3)", ctrl_metrics),
                     ("Full structured (parts 1+2+3)", struct_metrics)]:
        print(f"  {name:<30} {m['mrr']:8.4f} {m[f'precision_at_{n_correct}']:8.4f} {m['mean_rank']:10.1f} {m['ndcg']:8.4f}")

    # Control verification
    q_alignment_before = abs(np.dot(query_emb, control_vector))
    q_alignment_after = abs(np.dot(q_ctrl, control_vector))
    print(f"\n  Control verification:")
    print(f"    Query-control alignment: {q_alignment_before:.6f} -> {q_alignment_after:.2e}")

    return {
        "experiment": dataset["name"],
        "model": model_name,
        "embedding_dim": int(dim),
        "n_candidates": n_candidates,
        "n_correct": n_correct,
        "target_control_alignment": float(target_control_dot),
        "naive": naive_metrics,
        "control_only": ctrl_metrics,
        "structured": struct_metrics,
        "naive_improvement_over_ctrl": {
            "mrr_delta": ctrl_metrics["mrr"] - naive_metrics["mrr"],
        },
        "structured_improvement_over_naive": {
            "mrr_delta": struct_metrics["mrr"] - naive_metrics["mrr"],
        },
        "structured_improvement_over_ctrl": {
            "mrr_delta": struct_metrics["mrr"] - ctrl_metrics["mrr"],
        },
        "query_control_alignment_before": float(q_alignment_before),
        "query_control_alignment_after": float(q_alignment_after),
    }


def main():
    parser = argparse.ArgumentParser(description="Structured Matching Primitive — Full Implementation")
    parser.add_argument("--model", default="mxbai-embed-large",
                        choices=["mxbai-embed-large", "nomic-embed-text", "all-minilm"],
                        help="Embedding model to use")
    parser.add_argument("--all-models", action="store_true",
                        help="Run on all available models")
    parser.add_argument("--output", default=None,
                        help="Output JSON file for results")
    args = parser.parse_args()

    models = (["mxbai-embed-large", "nomic-embed-text", "all-minilm"]
              if args.all_models else [args.model])

    datasets = [
        get_countries_dataset(),
        get_occupations_dataset(),
        get_animals_dataset(),
    ]

    all_results = []

    for model_name in models:
        embed_fn, display_name = get_embedder(model_name)
        print(f"\n{'#'*70}")
        print(f"  MODEL: {display_name}")
        print(f"{'#'*70}")

        for dataset in datasets:
            try:
                result = run_experiment(dataset, embed_fn, display_name)
                all_results.append(result)
            except Exception as e:
                print(f"\n  ERROR on {dataset['name']}: {e}")
                import traceback
                traceback.print_exc()

    # Summary
    print(f"\n\n{'='*70}")
    print("  SUMMARY: Three Methods Compared")
    print(f"{'='*70}")
    print(f"  {'Model':<25} {'Dataset':<45} {'Naive':>6} {'Ctrl':>6} {'Full':>6}")
    print(f"  {'-'*25} {'-'*45} {'-'*6} {'-'*6} {'-'*6}")
    for r in all_results:
        print(f"  {r['model']:<25} {r['experiment'][:44]:<45} "
              f"{r['naive']['mrr']:>6.3f} {r['control_only']['mrr']:>6.3f} {r['structured']['mrr']:>6.3f}")

    # Overall improvements
    naive_mrrs = [r["naive"]["mrr"] for r in all_results]
    ctrl_mrrs = [r["control_only"]["mrr"] for r in all_results]
    struct_mrrs = [r["structured"]["mrr"] for r in all_results]

    n_ctrl_improved = sum(1 for c, n in zip(ctrl_mrrs, naive_mrrs) if c > n)
    n_struct_improved = sum(1 for s, n in zip(struct_mrrs, naive_mrrs) if s > n)
    n_struct_over_ctrl = sum(1 for s, c in zip(struct_mrrs, ctrl_mrrs) if s > c)

    print(f"\n  Control-only beats naive: {n_ctrl_improved}/{len(all_results)}")
    print(f"  Full structured beats naive: {n_struct_improved}/{len(all_results)}")
    print(f"  Full structured beats control-only: {n_struct_over_ctrl}/{len(all_results)}")
    print(f"  Mean MRR — naive: {np.mean(naive_mrrs):.4f}, ctrl: {np.mean(ctrl_mrrs):.4f}, full: {np.mean(struct_mrrs):.4f}")

    # Save
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "data", "structured_matching_results.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "structured_matching_primitive",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": all_results,
            "summary": {
                "n_experiments": len(all_results),
                "ctrl_beats_naive": n_ctrl_improved,
                "structured_beats_naive": n_struct_improved,
                "structured_beats_ctrl": n_struct_over_ctrl,
                "mean_mrr_naive": float(np.mean(naive_mrrs)),
                "mean_mrr_ctrl": float(np.mean(ctrl_mrrs)),
                "mean_mrr_structured": float(np.mean(struct_mrrs)),
            }
        }, f, indent=2)
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
