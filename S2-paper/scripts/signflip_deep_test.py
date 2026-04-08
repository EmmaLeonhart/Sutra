"""
S2 Sign-Flip Deep Testing
===========================
Now that sign-flip binding works, test it thoroughly:
1. Chained bundled operations (multi-step computation)
2. Cross-substrate (GTE, BGE, Jina)
3. Higher bundling capacity limits
4. Multi-role structure building and querying
5. Composition: unbind from one structure, bind into another
"""

import sys
import io
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


def embed_texts(model, tokenizer, texts, device='cpu'):
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')
    encoded = {k: v.to(device) for k, v in encoded.items()}
    with torch.no_grad():
        outputs = model(**encoded)
    attention_mask = encoded['attention_mask'].unsqueeze(-1).float()
    token_embeddings = outputs.last_hidden_state
    summed = (token_embeddings * attention_mask).sum(dim=1)
    counts = attention_mask.sum(dim=1)
    return (summed / counts).cpu().numpy()


def cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def snap_to_nearest(vector, codebook_matrix):
    diffs = codebook_matrix - vector
    dists = np.linalg.norm(diffs, axis=1)
    best_idx = np.argmin(dists)
    return codebook_matrix[best_idx], int(best_idx), float(dists[best_idx])


def bind_signflip(a, role):
    signs = np.sign(role)
    signs[signs == 0] = 1
    return a * signs

def unbind_signflip(bound, role):
    return bind_signflip(bound, role)  # self-inverse


def test_capacity_signflip(fillers, labels):
    """How many roles can we bundle with sign-flip before snap fails?"""
    print("\n=== SIGN-FLIP BUNDLING CAPACITY ===")
    dim = fillers.shape[1]
    n = len(fillers)
    codebook = np.array(fillers)
    np.random.seed(42)
    roles = np.random.randn(n, dim).astype(np.float32)

    print(f"  {'N roles':>7} | {'Raw cos':>8} | {'Snap?':>6} | {'Rank':>5}")
    print(f"  {'-'*7} | {'-'*8} | {'-'*6} | {'-'*5}")

    last_correct = 0
    for num_roles in range(1, min(n, 16)):
        structure = np.zeros(dim, dtype=np.float64)
        for i in range(num_roles):
            structure += bind_signflip(fillers[i].astype(np.float64), roles[i].astype(np.float64))

        recovered = unbind_signflip(structure, roles[0].astype(np.float64))
        raw_cos = cosine_similarity(recovered, fillers[0])
        snapped, snap_idx, _ = snap_to_nearest(recovered, codebook)
        correct = snap_idx == 0

        diffs = codebook - recovered
        dists = np.linalg.norm(diffs, axis=1)
        rank = int(np.where(np.argsort(dists) == 0)[0][0]) + 1

        if correct:
            last_correct = num_roles

        marker = "OK" if correct else "FAIL"
        print(f"  {num_roles:>7} | {raw_cos:>8.4f} | {marker:>6} | {rank:>5}")

    print(f"\n  Max roles with correct snap: {last_correct}")
    return last_correct


def test_chained_computation(fillers, labels):
    """
    Multi-step computation:
    Step 1: Build structure A = role1*filler1 + role2*filler2 + role3*filler3
    Step 2: Unbind filler1 from A, snap it
    Step 3: Build structure B = role4*recovered_filler1 + role5*filler4
    Step 4: Unbind recovered_filler1 from B, snap it
    Repeat. Does signal survive multiple structure-building cycles?
    """
    print("\n=== CHAINED BUNDLED COMPUTATION ===")
    print("Build structure → unbind → snap → build new structure → unbind → snap...")
    print("3 role-filler pairs per structure.\n")

    dim = fillers.shape[1]
    n = len(fillers)
    codebook = np.array(fillers)
    np.random.seed(42)
    roles = np.random.randn(30, dim).astype(np.float32)  # enough roles for 10 steps

    target = fillers[0]
    current = target.copy()
    role_idx = 0

    for step in range(1, 11):
        # Build structure with current + 2 distractors
        r1 = roles[role_idx]; role_idx += 1
        r2 = roles[role_idx]; role_idx += 1
        r3 = roles[role_idx]; role_idx += 1

        distractor1_idx = (step * 2) % n
        distractor2_idx = (step * 2 + 1) % n
        if distractor1_idx == 0: distractor1_idx = 1
        if distractor2_idx == 0: distractor2_idx = 2

        structure = (bind_signflip(current.astype(np.float64), r1.astype(np.float64)) +
                     bind_signflip(fillers[distractor1_idx].astype(np.float64), r2.astype(np.float64)) +
                     bind_signflip(fillers[distractor2_idx].astype(np.float64), r3.astype(np.float64)))

        # Unbind
        recovered = unbind_signflip(structure, r1.astype(np.float64))
        raw_cos = cosine_similarity(recovered, target)

        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest(recovered, codebook)
        correct = snap_idx == 0
        snap_cos = cosine_similarity(snapped, target)

        status = "CORRECT" if correct else f"WRONG → {labels[snap_idx]}"
        print(f"  Step {step:2d}: raw_cos={raw_cos:.4f}  snap_cos={snap_cos:.4f}  {status}")

        # Use snapped version for next step
        current = snapped

    return


def test_composition(fillers, labels):
    """
    Composition test: extract a filler from one structure, bind it into a different
    role in a new structure, then extract from the new structure.
    This is the fundamental operation for multi-hop reasoning.
    """
    print("\n=== COMPOSITION TEST (Multi-Hop) ===")
    print("Structure A: agent=cat, action=sit")
    print("Extract agent from A, insert as patient in B")
    print("Structure B: agent=dog, patient=<extracted_cat>")
    print("Extract patient from B — should recover 'cat'\n")

    dim = fillers.shape[1]
    codebook = np.array(fillers)
    np.random.seed(42)

    # Roles
    agent_role = np.random.randn(dim).astype(np.float32)
    action_role = np.random.randn(dim).astype(np.float32)
    patient_role = np.random.randn(dim).astype(np.float32)

    cat = fillers[0]    # "The cat sat on the mat"
    sit = fillers[1]    # "Dogs are loyal companions"
    dog = fillers[2]    # "Eiffel Tower..."

    # Structure A: agent=cat + action=sit
    struct_a = (bind_signflip(cat.astype(np.float64), agent_role.astype(np.float64)) +
                bind_signflip(sit.astype(np.float64), action_role.astype(np.float64)))

    # Extract agent from A
    recovered_cat = unbind_signflip(struct_a, agent_role.astype(np.float64))
    cos_step1 = cosine_similarity(recovered_cat, cat)
    snapped_cat, snap_idx1, _ = snap_to_nearest(recovered_cat, codebook)
    step1_correct = snap_idx1 == 0
    print(f"  Step 1 - Extract agent from A:")
    print(f"    cos to cat: {cos_step1:.4f}")
    print(f"    snap: {'CORRECT' if step1_correct else f'WRONG → {labels[snap_idx1]}'}")

    # Structure B: agent=dog + patient=recovered_cat
    struct_b = (bind_signflip(dog.astype(np.float64), agent_role.astype(np.float64)) +
                bind_signflip(snapped_cat.astype(np.float64), patient_role.astype(np.float64)))

    # Extract patient from B
    recovered_patient = unbind_signflip(struct_b, patient_role.astype(np.float64))
    cos_step2 = cosine_similarity(recovered_patient, cat)
    snapped_patient, snap_idx2, _ = snap_to_nearest(recovered_patient, codebook)
    step2_correct = snap_idx2 == 0
    print(f"\n  Step 2 - Extract patient from B:")
    print(f"    cos to cat: {cos_step2:.4f}")
    print(f"    snap: {'CORRECT' if step2_correct else f'WRONG → {labels[snap_idx2]}'}")

    # Also try extracting agent from B (should be dog)
    recovered_agent_b = unbind_signflip(struct_b, agent_role.astype(np.float64))
    cos_agent_b = cosine_similarity(recovered_agent_b, dog)
    snapped_agent_b, snap_idx3, _ = snap_to_nearest(recovered_agent_b, codebook)
    step3_correct = snap_idx3 == 2
    print(f"\n  Step 3 - Extract agent from B (should be 'Eiffel Tower/dog'):")
    print(f"    cos to dog: {cos_agent_b:.4f}")
    print(f"    snap: {'CORRECT' if step3_correct else f'WRONG → {labels[snap_idx3]}'}")

    print(f"\n  Composition {'WORKS' if (step1_correct and step2_correct and step3_correct) else 'PARTIAL' if (step1_correct and step2_correct) else 'FAILS'}")


def test_cross_substrate(model_names, device='cpu'):
    """Run sign-flip capacity test on multiple substrates."""
    print("\n=== CROSS-SUBSTRATE SIGN-FLIP TEST ===\n")

    test_texts = [
        "The cat sat on the mat",
        "Dogs are loyal companions",
        "The Eiffel Tower stands in Paris",
        "Quantum mechanics describes atomic behavior",
        "Shakespeare wrote Hamlet in 1600",
        "Neural networks learn from data",
        "The Pacific Ocean is the largest ocean",
        "Mozart composed symphonies in Vienna",
        "DNA carries genetic information",
        "Democracy means government by the people",
        "Photosynthesis converts sunlight to energy",
        "The Great Wall of China spans thousands of miles",
        "Black holes warp spacetime around them",
        "Coffee beans are roasted before grinding",
        "The Amazon rainforest produces oxygen",
    ]
    labels = [t[:30] + "..." if len(t) > 30 else t for t in test_texts]

    results = {}
    for model_name in model_names:
        print(f"\n--- {model_name} ---")
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name).to(device)
            model.eval()
            fillers = embed_texts(model, tokenizer, test_texts, device=device)
            capacity = test_capacity_signflip(fillers, labels)
            results[model_name] = capacity
            del model
            torch.cuda.empty_cache() if device == 'cuda' else None
        except Exception as e:
            print(f"  ERROR: {e}")
            results[model_name] = -1

    print("\n\n=== CROSS-SUBSTRATE SUMMARY ===")
    for name, cap in results.items():
        status = f"{cap} roles" if cap > 0 else "FAILED"
        print(f"  {name:<35}: {status}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--cross-substrate', action='store_true', help='Test multiple models')
    args = parser.parse_args()

    print(f"S2 Sign-Flip Deep Testing")
    print(f"=========================")

    if args.cross_substrate:
        models = [
            'thenlper/gte-large',
            'BAAI/bge-large-en-v1.5',
            'jinaai/jina-embeddings-v2-base-en',
        ]
        cross_results = test_cross_substrate(models, args.device)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, 'w') as f:
                json.dump(cross_results, f, indent=2)
        return

    # Default: deep test on GTE-large
    model_name = 'thenlper/gte-large'
    print(f"Model: {model_name}\n")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(args.device)
    model.eval()

    test_texts = [
        "The cat sat on the mat",
        "Dogs are loyal companions",
        "The Eiffel Tower stands in Paris",
        "Quantum mechanics describes atomic behavior",
        "Shakespeare wrote Hamlet in 1600",
        "Neural networks learn from data",
        "The Pacific Ocean is the largest ocean",
        "Mozart composed symphonies in Vienna",
        "DNA carries genetic information",
        "Democracy means government by the people",
        "Photosynthesis converts sunlight to energy",
        "The Great Wall of China spans thousands of miles",
        "Black holes warp spacetime around them",
        "Coffee beans are roasted before grinding",
        "The Amazon rainforest produces oxygen",
    ]
    labels = [t[:30] + "..." if len(t) > 30 else t for t in test_texts]

    fillers = embed_texts(model, tokenizer, test_texts, device=args.device)
    print(f"Shape: {fillers.shape}\n")

    test_capacity_signflip(fillers, labels)
    test_chained_computation(fillers, labels)
    test_composition(fillers, labels)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump({'model': model_name, 'status': 'complete'}, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
