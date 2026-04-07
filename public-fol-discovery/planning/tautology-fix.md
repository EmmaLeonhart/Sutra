# Fixing the "Tautology" Criticism

## The Criticism (appeared in 9 of 15 reviews)

The reviewer says our consistency-accuracy correlation (r=0.861) is a "mathematical tautology":
- "If vectors have high cosine alignment (consistency), the mean will naturally be a better predictor"
- "This is a geometric property, not a significant empirical discovery"

## What We Currently Do

### Phase 1: Operation Discovery (ALL data)
- For each predicate, compute `displacement = tail_vec - head_vec` for every triple
- Compute mean displacement vector from ALL triples
- Compute alignment: cosine similarity of each displacement with the mean
- Report `mean_alignment` as the "consistency score"

### Phase 2: Prediction Evaluation (leave-one-out)
- For each triple, recompute the mean displacement EXCLUDING that triple
- Predict: `head + leave_one_out_mean ≈ tail`
- Rank all entities by cosine similarity to the prediction
- Report MRR (Mean Reciprocal Rank)

### Phase 3: Composition (no leave-one-out)
- Find two-hop paths: S →P1→ M →P2→ O
- Predict: `S + op_P1 + op_P2 ≈ O`
- Report Hits@1, Hits@10

### The Problem
Phase 1 computes consistency on ALL triples. Phase 2 does leave-one-out for MRR.
Then we correlate consistency (from all data) with MRR (from leave-one-out).

The reviewer's complaint: consistency computed on all data is mathematically correlated
with leave-one-out prediction on the same data. Low-variance displacements will
naturally produce better leave-one-out means. This is partially true — it's not
a PURE tautology (leave-one-out does remove one data point), but it's not fully
independent either.

## The Fix: Proper Train/Test Split

### Approach
For each predicate with N triples:
1. **Randomly split** triples into 70% train / 30% test
2. **Compute consistency** (alignment) using ONLY the train set
3. **Compute the mean displacement** using ONLY the train set
4. **Evaluate MRR** using ONLY the test set (predict with train-set mean)
5. **Correlate** train-set consistency with test-set MRR

This makes the correlation a genuine empirical finding: "predicates whose
displacements are consistent on training data also predict accurately on
held-out data that was never used to compute anything."

### Implementation Details

```python
# For each predicate:
n = len(displacements)
n_train = int(n * 0.7)

# Shuffle indices
indices = np.random.permutation(n)
train_idx = indices[:n_train]
test_idx = indices[n_train:]

# Consistency from train set only
train_disps = displacements[train_idx]
train_mean = train_disps.mean(axis=0)
train_mean_unit = train_mean / (np.linalg.norm(train_mean) + 1e-10)
train_norms = np.linalg.norm(train_disps, axis=1, keepdims=True)
train_normed = train_disps / (train_norms + 1e-10)
train_alignment = float((train_normed @ train_mean_unit).mean())

# MRR from test set only, using train-set mean as the operator
for i in test_idx:
    subj_qid, obj_qid = triples[i]
    s_vec = qid_map[subj_qid][0]
    predicted = s_vec + train_mean  # <-- train-set operator
    # ... rank obj_qid among all entities ...
```

### Minimum Triple Threshold
- Need enough triples in both splits to be meaningful
- Current minimum: 10 triples → 7 train, 3 test (marginal)
- Could raise minimum to 15 or 20 for this analysis
- Or: report both the current leave-one-out AND the train/test split as separate analyses

### Multiple Random Splits
For robustness, run K random splits (e.g., K=10) and report:
- Mean correlation across splits
- Standard deviation of correlation
- This shows the result is stable, not dependent on a lucky split

### What We Expect
If the correlation is real (not tautological), we should see:
- r still significantly positive on held-out data (maybe r=0.7-0.8 instead of 0.861)
- Slight drop from leave-one-out r is expected and honest
- Bootstrap CI still above zero

If the correlation drops to near zero on held-out data, the reviewer was right
and we need to rethink that claim.

## Impact on the Paper

### Sections to update:
- Section 4.2 (Prediction Accuracy): add train/test results alongside leave-one-out
- Section 5.1 (Self-Diagnostic): reframe the correlation as cross-validated
- Abstract: update the r value if it changes
- Figure 1: regenerate with train/test data points

### New claim (much stronger):
"Displacement consistency computed on a training subset predicts prediction
accuracy on held-out triples with r = [X] (95% CI [Y, Z] across 10 random
splits). This demonstrates that consistency is a genuine predictive signal,
not a mathematical artifact of the evaluation procedure."

## Also Fix for Composition (Phase 3)

Currently composition uses operations computed from ALL data, then tests on
triples that were part of that computation.

Better: compute operation vectors from train split, test composition on
held-out two-hop paths where at least one hop uses a test-set triple.

This is harder to implement (need to track which triples are train vs test
across predicates) but would strengthen the composition claim too.

## Priority
HIGH — this kills the #2 most common criticism (9 of 15 reviews).
Relatively small code change. Big impact on reviewer perception.
