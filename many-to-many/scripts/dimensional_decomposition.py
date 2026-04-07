"""
Dimensional Decomposition for Many-to-Many Matching in Embedding Spaces
========================================================================

Demonstrates the structured matching primitive:
  1. Active selection  — maximize similarity along a target direction
  2. Active control    — orthogonally project away confounding dimensions
  3. Residual similarity — cosine on the residual, uncorrelated with controlled dims

Works on ANY embedding space. Tested on:
  - Language embeddings (Ollama: mxbai-embed-large, nomic-embed-text, all-minilm)
  - Biomedical embeddings (BioBERT via HuggingFace transformers)

Usage:
    python dimensional_decomposition.py
    python dimensional_decomposition.py --model mxbai-embed-large
    python dimensional_decomposition.py --model biobert
    python dimensional_decomposition.py --all-models
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
# Embedding backends
# ============================================================

def embed_ollama(texts, model="mxbai-embed-large"):
    """Embed texts via Ollama API."""
    import ollama
    result = ollama.embed(model=model, input=texts)
    return np.array(result.embeddings)


_biobert_model = None
_biobert_tokenizer = None

def embed_biobert(texts, model="dmis-lab/biobert-base-cased-v1.2"):
    """Embed texts via BioBERT (HuggingFace transformers + PyTorch)."""
    global _biobert_model, _biobert_tokenizer
    import torch
    from transformers import AutoTokenizer, AutoModel

    if _biobert_model is None:
        print(f"  Loading {model}...")
        _biobert_tokenizer = AutoTokenizer.from_pretrained(model)
        _biobert_model = AutoModel.from_pretrained(model)
        _biobert_model.eval()

    with torch.no_grad():
        encoded = _biobert_tokenizer(
            texts, padding=True, truncation=True,
            max_length=512, return_tensors="pt"
        )
        outputs = _biobert_model(**encoded)
        # Mean pooling over token embeddings
        mask = encoded["attention_mask"].unsqueeze(-1).float()
        embeddings = (outputs.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1)
    return embeddings.numpy()


def get_embedder(model_name):
    """Return (embed_fn, display_name, dim) for a given model name."""
    if model_name == "biobert":
        return embed_biobert, "BioBERT (biomedical)", 768
    else:
        return lambda texts: embed_ollama(texts, model=model_name), f"Ollama/{model_name}", None


# ============================================================
# Core primitive: orthogonal projection
# ============================================================

def compute_control_vector(embeddings_group_a, embeddings_group_b):
    """
    Derive a control vector as the mean displacement between two groups.
    This captures the dimension that separates the groups.
    """
    mean_a = np.mean(embeddings_group_a, axis=0)
    mean_b = np.mean(embeddings_group_b, axis=0)
    direction = mean_a - mean_b
    # Normalize
    norm = np.linalg.norm(direction)
    if norm < 1e-10:
        return direction
    return direction / norm


def project_away(embeddings, control_vector):
    """
    Remove the component along control_vector from each embedding.
    e_residual = e - (e . v / v . v) * v
    """
    v = control_vector
    vv = np.dot(v, v)
    if vv < 1e-10:
        return embeddings.copy()
    projections = (embeddings @ v) / vv
    return embeddings - np.outer(projections, v)


def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    return 1.0 - cosine_dist(a, b)


def rank_by_similarity(query, candidates, candidate_labels):
    """Rank candidates by cosine similarity to query. Return (label, score) list."""
    scores = [(label, cosine_sim(query, cand))
              for label, cand in zip(candidate_labels, candidates)]
    return sorted(scores, key=lambda x: -x[1])


# ============================================================
# Experiment datasets
# ============================================================

def get_biomedical_dataset():
    """
    Biomedical entities with known confounders.

    Groups: cancer-related vs. cardiovascular-related proteins,
    with organism (human vs. mouse) as a confounder.

    The test: when descriptions are dominated by organism-specific context,
    can we recover functional similarity by projecting away the organism dimension?
    """
    return {
        "name": "Biomedical: Protein Function vs. Organism Context",
        "description": (
            "Cancer vs. cardiovascular proteins. Organism context (human clinical "
            "vs. mouse model) dominates the descriptions. Goal: find functionally "
            "similar proteins regardless of organism framing."
        ),
        # Human clinical descriptions
        "group_a_labels": [
            "human patient clinical trial oncology chemotherapy hospital treatment",
            "patient tumor biopsy surgical resection clinical outcome prognosis",
            "human breast cancer screening mammography clinical diagnosis staging",
            "patient blood draw serum biomarker clinical laboratory hospital",
            "human clinical pharmacology drug dosing adverse events trial safety",
        ],
        # Mouse model descriptions
        "group_b_labels": [
            "mouse model xenograft tumor implantation nude mice laboratory",
            "murine knockout transgenic phenotype embryonic development colony",
            "mouse brain dissection tissue homogenate protein extraction assay",
            "murine bone marrow transplant irradiated recipient donor cells",
            "mouse behavioral test Morris water maze rotarod locomotor activity",
        ],
        "confounder_a_labels": None,  # Use group_a/group_b as confounder
        "confounder_b_labels": None,
        # Query: cancer protein described in mouse context
        "query": "TP53 tumor suppressor apoptosis cell cycle arrest studied in transgenic mouse model knockout phenotype embryonic lethality",
        # Candidates: cancer proteins in human context (correct but organism-mismatched)
        # vs. cardiovascular proteins in mouse context (wrong but organism-matched)
        "candidates": [
            # Cancer proteins described in HUMAN context (correct function, wrong organism)
            ("BRCA1 DNA repair breast cancer risk human patient clinical genetic counseling screening", "cancer", "human"),
            ("EGFR epidermal growth factor receptor lung cancer human patient targeted therapy clinical", "cancer", "human"),
            ("KRAS oncogene mutation human colorectal cancer patient clinical sequencing prognosis", "cancer", "human"),
            ("MYC proto-oncogene transcription factor human lymphoma patient clinical treatment outcome", "cancer", "human"),
            # Cancer proteins described in MOUSE context (correct function, matched organism)
            ("RB1 retinoblastoma tumor suppressor mouse knockout model embryonic development phenotype", "cancer", "mouse"),
            # Cardiovascular proteins in MOUSE context (wrong function, matched organism)
            ("VEGF vascular endothelial growth factor angiogenesis mouse model knockout embryonic lethality", "cardiovascular", "mouse"),
            ("ACE2 angiotensin converting enzyme mouse model hypertension cardiac remodeling transgenic", "cardiovascular", "mouse"),
            ("NOS3 endothelial nitric oxide synthase mouse knockout vascular dysfunction phenotype", "cardiovascular", "mouse"),
            ("KCNQ1 potassium channel cardiac arrhythmia mouse model long QT syndrome knockout", "cardiovascular", "mouse"),
            ("PLN phospholamban calcium handling mouse model dilated cardiomyopathy transgenic heart failure", "cardiovascular", "mouse"),
        ],
        "correct_category": "cancer",
    }


def get_hiring_dataset():
    """
    Hiring / labor matching with gender as a confounder.

    The test: when gender-coded language dominates candidate descriptions,
    can we recover role fitness by projecting away the gender dimension?
    Descriptions are deliberately heavy on gender context to create real conflation.
    """
    return {
        "name": "Labor Matching: Role Fitness vs. Gender Coding",
        "description": (
            "Software engineering candidates. Descriptions are heavy on "
            "gendered framing. Goal: find best role-fit candidates regardless "
            "of gender signals in the description."
        ),
        "group_a_labels": [
            "he him his men boys male masculine fraternity brotherhood man",
            "father son husband gentleman king prince patriarch manly masculine",
            "he built machines in his garage with his father and brothers",
            "the men competed fiercely in the wrestling championship tournament",
            "his deep voice commanded the room as the chairman spoke firmly",
        ],
        "group_b_labels": [
            "she her hers women girls female feminine sorority sisterhood woman",
            "mother daughter wife lady queen princess matriarch womanly feminine",
            "she organized the quilting circle with her mother and sisters",
            "the women gathered for the bridal shower celebration together",
            "her gentle voice carried through the room as the chairwoman spoke",
        ],
        "confounder_a_labels": None,
        "confounder_b_labels": None,
        # Query: male-framed software engineer
        "query": "he is a senior software engineer with 10 years building distributed systems in Go and Python at his previous company where he led the backend team",
        "candidates": [
            # Female software engineers (correct role, gender-mismatched to query)
            ("she is a staff software engineer who built microservices architecture at her company using Python and Kubernetes for the past 12 years as the women in tech lead", "software_eng", "female"),
            ("her expertise is distributed systems and she architected the real-time data pipeline as a principal engineer at her previous firm", "software_eng", "female"),
            ("she writes Go and Rust building high performance backends and she mentors other women in engineering at her organization", "software_eng", "female"),
            # Male non-engineers (wrong role, gender-matched to query)
            ("he is a senior sales manager who leads his team of account executives and he built the outbound sales process from scratch at his company", "sales", "male"),
            ("he works as a construction foreman managing his crew of builders and he has 15 years leading men on commercial building projects", "construction", "male"),
            ("he is a financial analyst at his investment firm where he builds Excel models and he advises his clients on portfolio strategy", "finance", "male"),
            # Female non-engineers (wrong role, gender-mismatched)
            ("she is a marketing director who leads her team of content creators and she built the brand strategy at her company", "marketing", "female"),
            ("she works as a human resources manager coordinating her team of recruiters and she handles employee relations at her organization", "hr", "female"),
            # Male software engineers (correct role, gender-matched — baseline)
            ("he is a backend engineer with 8 years of experience building APIs in Go and Python and he leads his team of developers", "software_eng", "male"),
            ("he architects distributed systems as a senior engineer and he has built several high-throughput data processing pipelines at his firm", "software_eng", "male"),
        ],
        "correct_category": "software_eng",
    }


def get_ontology_dataset():
    """
    Wikidata-style ontological entities with domain/register as confounder.

    The test: entities that are functionally similar (all types of "leader")
    but described in very different domain registers (religious vs. military
    vs. corporate). Can we find leadership-similar entities when domain
    language dominates the embedding?
    """
    return {
        "name": "Ontology: Functional Role vs. Domain Register",
        "description": (
            "Leadership roles across domains (religious, military, corporate, academic). "
            "Domain-specific language dominates descriptions. "
            "Goal: find role-similar leaders regardless of domain."
        ),
        # Religious register
        "group_a_labels": [
            "temple shrine church mosque synagogue prayer worship ceremony ritual altar sacred divine holy",
            "scripture canon sutra dharma gospel theology doctrine faith revelation blessing salvation",
            "monk priest imam rabbi nun clergy ordination monastery parish diocese consecrated",
            "pilgrimage meditation fasting penance devotion contemplation spiritual retreat sanctuary",
            "sermon homily prayer chanting liturgy vespers matins psalm hymn incantation",
        ],
        # Military register
        "group_b_labels": [
            "barracks base battalion regiment brigade division platoon corps garrison fort deployment",
            "weapon rifle artillery missile tank fighter jet bomber submarine warship ammunition",
            "soldier marine sergeant lieutenant colonel general admiral private recruit cadet officer",
            "campaign offensive reconnaissance surveillance intelligence counterinsurgency operations",
            "combat engagement patrol mission sortie convoy airstrike maneuver flanking formation",
        ],
        "confounder_a_labels": None,
        "confounder_b_labels": None,
        # Query: a religious leader
        "query": "the abbot leads the monastic community overseeing daily operations setting spiritual direction and managing administrative affairs of the monastery",
        "candidates": [
            # Military leaders (correct: leadership role, wrong domain)
            ("the general commands the division overseeing tactical operations setting strategic direction and managing logistics of the campaign", "leader", "military"),
            ("the admiral leads the naval fleet coordinating operations across carrier groups and managing force deployment", "leader", "military"),
            ("the colonel oversees the regiment directing training programs setting operational goals and managing battalion resources", "leader", "military"),
            # Corporate leaders (correct: leadership role, different domain)
            ("the CEO leads the company overseeing daily operations setting strategic direction and managing corporate affairs", "leader", "corporate"),
            ("the managing director oversees the firm directing business strategy and coordinating department heads", "leader", "corporate"),
            # Religious non-leaders (wrong role, matched domain)
            ("the novice monk sweeps the temple courtyard carrying water for the kitchen and studying scripture each evening", "non_leader", "religious"),
            ("the pilgrim walks the sacred path visiting holy shrines and offering prayers at each station", "non_leader", "religious"),
            ("the acolyte assists at the altar preparing incense and sacred vessels for the worship service", "non_leader", "religious"),
            # Military non-leaders (wrong role, wrong domain)
            ("the private cleans his rifle in the barracks and follows orders from his commanding officer", "non_leader", "military"),
            ("the recruit runs drills on the parade ground doing pushups and learning to march in formation", "non_leader", "military"),
        ],
        "correct_category": "leader",
    }


# ============================================================
# Run experiment
# ============================================================

def run_experiment(dataset, embed_fn, model_name):
    """
    Run the dimensional decomposition experiment on a dataset.

    Returns dict with results.
    """
    print(f"\n{'='*70}")
    print(f"  {dataset['name']}")
    print(f"  Model: {model_name}")
    print(f"{'='*70}")
    print(f"  {dataset['description']}\n")

    # Collect all texts to embed in one batch
    all_texts = []
    all_texts.extend(dataset["group_a_labels"])
    all_texts.extend(dataset["group_b_labels"])

    conf_a = dataset["confounder_a_labels"] or dataset["group_a_labels"]
    conf_b = dataset["confounder_b_labels"] or dataset["group_b_labels"]
    if dataset["confounder_a_labels"]:
        all_texts.extend(conf_a)
        all_texts.extend(conf_b)

    all_texts.append(dataset["query"])
    candidate_texts = [c[0] for c in dataset["candidates"]]
    all_texts.extend(candidate_texts)

    print(f"  Embedding {len(all_texts)} texts...")
    t0 = time.time()
    all_embeddings = embed_fn(all_texts)
    t1 = time.time()
    dim = all_embeddings.shape[1]
    print(f"  Done in {t1-t0:.1f}s ({dim}-dimensional embeddings)\n")

    # Unpack embeddings
    idx = 0
    n_a = len(dataset["group_a_labels"])
    n_b = len(dataset["group_b_labels"])
    group_a_emb = all_embeddings[idx:idx+n_a]; idx += n_a
    group_b_emb = all_embeddings[idx:idx+n_b]; idx += n_b

    if dataset["confounder_a_labels"]:
        n_ca = len(conf_a)
        n_cb = len(conf_b)
        conf_a_emb = all_embeddings[idx:idx+n_ca]; idx += n_ca
        conf_b_emb = all_embeddings[idx:idx+n_cb]; idx += n_cb
    else:
        conf_a_emb = group_a_emb
        conf_b_emb = group_b_emb

    query_emb = all_embeddings[idx]; idx += 1
    candidate_embs = all_embeddings[idx:idx+len(dataset["candidates"])]

    # Derive control vector
    control_vector = compute_control_vector(conf_a_emb, conf_b_emb)

    # --- Naive ranking (full cosine similarity) ---
    candidate_labels = [f"{c[0][:60]}... [{c[1]}/{c[2]}]" for c in dataset["candidates"]]
    candidate_categories = [c[1] for c in dataset["candidates"]]

    naive_ranking = rank_by_similarity(query_emb, candidate_embs, candidate_labels)

    print("  NAIVE RANKING (full cosine similarity):")
    naive_correct_ranks = []
    for rank, (label, score) in enumerate(naive_ranking, 1):
        idx_in_candidates = candidate_labels.index(label)
        cat = candidate_categories[idx_in_candidates]
        marker = " <-- correct" if cat == dataset["correct_category"] else ""
        print(f"    {rank:2d}. [{score:.4f}] {label}{marker}")
        if cat == dataset["correct_category"]:
            naive_correct_ranks.append(rank)

    # --- Projected ranking (control vector removed) ---
    query_projected = project_away(query_emb.reshape(1, -1), control_vector)[0]
    candidates_projected = project_away(candidate_embs, control_vector)

    projected_ranking = rank_by_similarity(query_projected, candidates_projected, candidate_labels)

    print(f"\n  PROJECTED RANKING (confounder dimension removed):")
    projected_correct_ranks = []
    for rank, (label, score) in enumerate(projected_ranking, 1):
        idx_in_candidates = candidate_labels.index(label)
        cat = candidate_categories[idx_in_candidates]
        marker = " <-- correct" if cat == dataset["correct_category"] else ""
        print(f"    {rank:2d}. [{score:.4f}] {label}{marker}")
        if cat == dataset["correct_category"]:
            projected_correct_ranks.append(rank)

    # --- Metrics ---
    naive_mrr = np.mean([1.0/r for r in naive_correct_ranks])
    projected_mrr = np.mean([1.0/r for r in projected_correct_ranks])

    n_correct = len(naive_correct_ranks)
    naive_precision_at_k = sum(1 for r in naive_correct_ranks if r <= n_correct) / n_correct
    projected_precision_at_k = sum(1 for r in projected_correct_ranks if r <= n_correct) / n_correct

    naive_mean_rank = np.mean(naive_correct_ranks)
    projected_mean_rank = np.mean(projected_correct_ranks)

    # Control vector analysis
    query_alignment = abs(np.dot(query_emb, control_vector))
    residual_alignment = abs(np.dot(query_projected, control_vector))

    print(f"\n  METRICS:")
    print(f"    Mean Reciprocal Rank (MRR):  naive={naive_mrr:.4f}  projected={projected_mrr:.4f}  delta={projected_mrr-naive_mrr:+.4f}")
    print(f"    Precision@{n_correct}:               naive={naive_precision_at_k:.4f}  projected={projected_precision_at_k:.4f}  delta={projected_precision_at_k-naive_precision_at_k:+.4f}")
    print(f"    Mean rank of correct items:  naive={naive_mean_rank:.1f}      projected={projected_mean_rank:.1f}      delta={projected_mean_rank-naive_mean_rank:+.1f}")
    print(f"    Query-control alignment:     before={query_alignment:.6f}  after={residual_alignment:.2e}")
    print(f"    Control vector norm:         {np.linalg.norm(control_vector):.6f}")

    return {
        "experiment": dataset["name"],
        "model": model_name,
        "embedding_dim": dim,
        "n_candidates": len(dataset["candidates"]),
        "n_correct": n_correct,
        "naive_mrr": float(naive_mrr),
        "projected_mrr": float(projected_mrr),
        "mrr_improvement": float(projected_mrr - naive_mrr),
        "naive_precision": float(naive_precision_at_k),
        "projected_precision": float(projected_precision_at_k),
        "precision_improvement": float(projected_precision_at_k - naive_precision_at_k),
        "naive_mean_rank": float(naive_mean_rank),
        "projected_mean_rank": float(projected_mean_rank),
        "rank_improvement": float(naive_mean_rank - projected_mean_rank),
        "naive_correct_ranks": naive_correct_ranks,
        "projected_correct_ranks": projected_correct_ranks,
        "query_control_alignment_before": float(query_alignment),
        "query_control_alignment_after": float(residual_alignment),
    }


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Dimensional Decomposition Demo")
    parser.add_argument("--model", default="mxbai-embed-large",
                        choices=["mxbai-embed-large", "nomic-embed-text", "all-minilm", "biobert"],
                        help="Embedding model to use")
    parser.add_argument("--all-models", action="store_true",
                        help="Run on all available models")
    parser.add_argument("--output", default=None,
                        help="Output JSON file for results")
    args = parser.parse_args()

    models = (["mxbai-embed-large", "nomic-embed-text", "all-minilm", "biobert"]
              if args.all_models else [args.model])

    datasets = [
        get_biomedical_dataset(),
        get_hiring_dataset(),
        get_ontology_dataset(),
    ]

    all_results = []

    for model_name in models:
        embed_fn, display_name, _ = get_embedder(model_name)
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

    # Summary table
    print(f"\n\n{'='*70}")
    print("  SUMMARY: MRR Improvement from Dimensional Decomposition")
    print(f"{'='*70}")
    print(f"  {'Model':<30} {'Experiment':<45} {'Naive':>6} {'Proj':>6} {'Delta':>7}")
    print(f"  {'-'*30} {'-'*45} {'-'*6} {'-'*6} {'-'*7}")
    for r in all_results:
        print(f"  {r['model']:<30} {r['experiment']:<45} {r['naive_mrr']:>6.3f} {r['projected_mrr']:>6.3f} {r['mrr_improvement']:>+7.3f}")

    # Overall stats
    improvements = [r["mrr_improvement"] for r in all_results]
    positive = sum(1 for i in improvements if i > 0)
    print(f"\n  Improvement in {positive}/{len(improvements)} experiments")
    if improvements:
        print(f"  Mean MRR improvement: {np.mean(improvements):+.4f}")
        print(f"  Max MRR improvement:  {np.max(improvements):+.4f}")

    # Save results
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "data", "decomposition_results.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "dimensional_decomposition",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": all_results,
            "summary": {
                "n_experiments": len(all_results),
                "n_improved": positive,
                "mean_mrr_improvement": float(np.mean(improvements)) if improvements else 0,
                "max_mrr_improvement": float(np.max(improvements)) if improvements else 0,
            }
        }, f, indent=2)
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
