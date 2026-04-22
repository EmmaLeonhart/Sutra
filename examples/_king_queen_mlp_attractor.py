"""MLP-backed attractor search over king - man + woman on nomic-embed-text.

This is the real Monte-Carlo attractor search the user described on
2026-04-22 (not the random-rotation-plus-nearest-neighbor script next
door — that one is a fragility check, not attractor dynamics).

Mechanism:

1. Train an MLP f: R^768 -> R^768 with a skip connection,
     f(x) = x + residual(x),
   whose objective is to pull perturbed versions of the codebook
   vectors back toward their unperturbed originals. The codebook
   vectors become fixed points; their neighborhoods are basins of
   attraction. This is a denoising-autoencoder formulation —
   standard Hopfield-inspired attractor learning.
2. Starting from v0 = king - man + woman (the naive analogy vector),
   iterate f repeatedly. The trajectory walks through the learned
   landscape and settles into whichever basin v0 falls inside.
3. Monte-Carlo sweep: run N trajectories starting from v0 + small
   noise to see how the basin distribution looks under perturbation.
   A robust naive-analogy result would land all N trajectories in
   queen's basin; a fragile one scatters between queen and king (or
   other near-neighbors).

Substrate: nomic-embed-text via Ollama, 768-dim, mean-centered per
the default codegen config. User direction 2026-04-22: nomic is the
chosen substrate because the cross-substrate sweep
(_king_queen_multi_substrate.py) showed it's the only one of the
three tested where queen wins naively. The attractor search is a
follow-on: given that naive-queen works, does an attractor-trained
MLP give a MORE robust queen (larger basin, broader Monte-Carlo
recovery) or not?

Usage: python examples/_king_queen_mlp_attractor.py

Training runs on GPU if available; ~30 seconds end-to-end on
CPU too. Writes no files — reports to stdout.
"""
from __future__ import annotations

import os
import sys
import types
from collections import Counter

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen_numpy import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

SEED = 42
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Fix RNG state for reproducibility. Nomic embedding lookups are
# deterministic via Ollama's cache, so the only source of randomness
# is the MLP init + training data sampling + MC perturbation draws.
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


class AttractorMLP(nn.Module):
    """Residual MLP f(x) = x + r(x) for attractor dynamics.

    Skip connection means the identity is the default; learning only
    has to fit small corrections. This is important for stability
    under iteration — without the skip, a random-init MLP output has
    arbitrary magnitude and iterating pulls trajectories far from
    the embedding manifold immediately.
    """

    def __init__(self, dim: int, hidden: int = 512) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, dim),
        )
        # Zero-init the final layer so f(x) = x at init — clean start.
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.net(x)


def compile_king_queen() -> types.ModuleType:
    """Compile examples/king_queen_naive.su to get nomic-embedded vectors."""
    path = os.path.join(HERE, "king_queen_naive.su")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType("_kq_mlp")
    mod.__file__ = "<mlp attractor>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def build_codebook(mod) -> tuple[list[str], np.ndarray]:
    """Return (names, stacked_vectors). Vectors are normalized
    by the codegen already (L2 = 1 after mean-center + normalize)."""
    names = ["king", "queen", "man", "woman", "prince", "princess",
             "boy", "girl", "ruler", "monarch", "husband", "wife",
             "father", "mother"]
    vecs = np.stack([getattr(mod, n) for n in names]).astype(np.float32)
    return names, vecs


def make_training_data(
    codebook: np.ndarray,
    samples_per_vec: int = 500,
    eps_range: tuple[float, float] = (0.05, 0.40),
) -> tuple[torch.Tensor, torch.Tensor]:
    """Noisy inputs with clean codebook targets.

    For each codebook vector c, draw random perturbations c + eps*n
    at various eps. Target is c itself (pull back to the attractor).
    """
    Xs = []
    Ys = []
    dim = codebook.shape[1]
    for c in codebook:
        for _ in range(samples_per_vec):
            eps = np.random.uniform(*eps_range)
            n = np.random.randn(dim).astype(np.float32)
            # Normalize n to unit length; no orthogonalization needed —
            # the attractor should pull back from any direction
            n = n / (np.linalg.norm(n) + 1e-12)
            Xs.append(c + eps * n)
            Ys.append(c)
    X = torch.tensor(np.array(Xs), dtype=torch.float32)
    Y = torch.tensor(np.array(Ys), dtype=torch.float32)
    return X, Y


def train_attractor_mlp(
    codebook: np.ndarray,
    epochs: int = 3000,
    batch_size: int = 256,
    lr: float = 1e-3,
) -> AttractorMLP:
    dim = codebook.shape[1]
    X, Y = make_training_data(codebook, samples_per_vec=500)
    X, Y = X.to(DEVICE), Y.to(DEVICE)

    model = AttractorMLP(dim=dim, hidden=512).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=lr)
    n = X.shape[0]

    print(f"Training attractor MLP on {codebook.shape[0]} codebook vectors"
          f" ({n} noisy samples, {epochs} epochs) on {DEVICE}...")
    for epoch in range(epochs):
        idx = torch.randperm(n, device=DEVICE)[:batch_size]
        pred = model(X[idx])
        loss = ((pred - Y[idx]) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if epoch % 500 == 0 or epoch == epochs - 1:
            print(f"  epoch {epoch:4d}  loss={loss.item():.5f}")
    return model


def iterate(model: AttractorMLP, v0: np.ndarray, n_steps: int) -> list[np.ndarray]:
    """Run the trajectory v_{i+1} = f(v_i) for n_steps."""
    traj = [v0.copy()]
    v = torch.tensor(v0, dtype=torch.float32, device=DEVICE).unsqueeze(0)
    with torch.no_grad():
        for _ in range(n_steps):
            v = model(v)
            traj.append(v.squeeze().cpu().numpy())
    return traj


def nearest_in_codebook(v: np.ndarray, names: list[str], codebook: np.ndarray) -> tuple[str, float]:
    sims = codebook @ v / (np.linalg.norm(codebook, axis=1) * np.linalg.norm(v) + 1e-12)
    i = int(np.argmax(sims))
    return names[i], float(sims[i])


def fixed_point_report(model: AttractorMLP, names: list[str], codebook: np.ndarray) -> None:
    """How close is f(c_i) to c_i for each codebook entry?"""
    print("\nFixed-point quality (smaller ||f(c) - c|| = tighter attractor):")
    X = torch.tensor(codebook, dtype=torch.float32, device=DEVICE)
    with torch.no_grad():
        Y = model(X).cpu().numpy()
    for i, name in enumerate(names):
        err = float(np.linalg.norm(Y[i] - codebook[i]))
        drift = Y[i] - codebook[i]
        # Where does f(c_i) drift toward? (excluding c_i itself)
        nbrs = [(n, float((Y[i] @ codebook[j]) /
                          (np.linalg.norm(Y[i]) * np.linalg.norm(codebook[j]) + 1e-12)))
                for j, n in enumerate(names) if j != i]
        nbrs.sort(key=lambda x: -x[1])
        top_neighbor = nbrs[0]
        print(f"  {name:<10}  ||f(c) - c|| = {err:.4f}"
              f"   top-other-neighbor={top_neighbor[0]}({top_neighbor[1]:+.3f})")


def basin_report(model: AttractorMLP, v0: np.ndarray,
                 names: list[str], codebook: np.ndarray,
                 n_steps: int = 30) -> str:
    """Where does v0 converge to? Trajectory report."""
    traj = iterate(model, v0, n_steps)
    print(f"\nTrajectory from v0 (king - man + woman), {n_steps} steps:")
    # Show the first 3 steps plus every 5th
    show_steps = [0, 1, 2, 3] + list(range(5, n_steps + 1, 5))
    for i in show_steps:
        if i > n_steps:
            break
        name, sim = nearest_in_codebook(traj[i], names, codebook)
        # Also compute the magnitude of the step to see if we've converged
        if i > 0:
            delta = np.linalg.norm(traj[i] - traj[i - 1])
        else:
            delta = float("nan")
        print(f"  step {i:3d}  nearest={name:<10} sim={sim:+.3f}"
              f"   step_size={delta:.4f}")
    final_name, final_sim = nearest_in_codebook(traj[-1], names, codebook)
    print(f"  FINAL    nearest={final_name:<10} sim={final_sim:+.3f}")
    return final_name


def monte_carlo_basin(
    model: AttractorMLP,
    v0: np.ndarray,
    names: list[str],
    codebook: np.ndarray,
    n_trials: int,
    noise_std: float,
    n_steps: int,
    rng: np.random.RandomState,
) -> Counter:
    """N trials: perturb v0 by Gaussian noise, iterate to convergence,
    record which codebook entry the trajectory ends nearest to."""
    winners: Counter = Counter()
    for _ in range(n_trials):
        v_perturbed = v0 + noise_std * rng.randn(v0.shape[0]).astype(np.float32)
        traj = iterate(model, v_perturbed, n_steps)
        winner, _ = nearest_in_codebook(traj[-1], names, codebook)
        winners[winner] += 1
    return winners


def print_histogram(name: str, winners: Counter, total: int) -> None:
    print(f"\n{name}:")
    for nm, count in winners.most_common():
        bar = "#" * int(40 * count / total)
        pct = 100.0 * count / total
        print(f"  {nm:<10} {count:3} ({pct:5.1f}%) {bar}")


def main() -> int:
    print("=" * 72)
    print("MLP-backed attractor search over king - man + woman")
    print("Substrate: nomic-embed-text (user direction 2026-04-22)")
    print("=" * 72)

    # Load the codebook and the naive analogy vector from the .su program
    print("\nLoading king_queen_naive.su (compiles, pulls nomic embeddings)...")
    mod = compile_king_queen()
    names, codebook = build_codebook(mod)
    v0 = mod.analogy.astype(np.float32)  # king - man + woman, L2-normalized
    print(f"  Loaded codebook: {len(names)} vectors of dim {codebook.shape[1]}.")

    # Baseline (what naive analogy returns, for comparison)
    baseline_name, baseline_sim = nearest_in_codebook(v0, names, codebook)
    print(f"\nBaseline (no attractor): argmax_cosine(v0, codebook) = "
          f"{baseline_name} (cos={baseline_sim:+.4f})")

    # Train the attractor MLP
    model = train_attractor_mlp(codebook, epochs=3000)

    # Check fixed-point quality
    fixed_point_report(model, names, codebook)

    # Run the trajectory from v0 and see where it converges
    final_name = basin_report(model, v0, names, codebook, n_steps=30)

    # Monte-Carlo basin sweep at multiple noise scales
    print("\n" + "=" * 72)
    print("Monte-Carlo basin sweep")
    print("=" * 72)
    print(f"{200} trajectories per noise-scale; each starts at v0 + noise,")
    print(f"iterates the attractor MLP for 30 steps, then snaps to nearest codebook.")
    rng = np.random.RandomState(SEED + 7)
    for noise_std in [0.00, 0.05, 0.15, 0.30]:
        winners = monte_carlo_basin(
            model, v0, names, codebook,
            n_trials=200, noise_std=noise_std, n_steps=30, rng=rng,
        )
        print_histogram(f"noise_std = {noise_std:.2f}", winners, 200)

    # Summary
    print("\n" + "=" * 72)
    print("Summary")
    print("=" * 72)
    print(f"  Baseline (argmax cosine of v0):     {baseline_name}")
    print(f"  MLP attractor converges v0 to:      {final_name}")
    if final_name == "queen":
        print("  -> attractor CONFIRMS naive winner (queen).")
    elif baseline_name == final_name:
        print("  -> attractor and baseline agree but neither is queen.")
    else:
        print(f"  -> attractor DISAGREES with baseline "
              f"(baseline={baseline_name}, attractor={final_name}).")
    print()
    print("Interpretation:")
    print("- The MLP is trained so the 14 codebook vectors are fixed points,")
    print("  i.e. f(c_i) ~= c_i. Noisy perturbations get pulled back toward")
    print("  their respective attractors. The basin each trajectory lands in")
    print("  is determined by the TRAJECTORY (iteration dynamics), not just")
    print("  the initial nearest-neighbor.")
    print("- If the Monte-Carlo sweep scatters across multiple attractors at")
    print("  low noise, v0 is sitting near a basin boundary (geometrically")
    print("  fragile). If it stays locked on one attractor until high noise,")
    print("  v0 is deep inside one basin (geometrically robust).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
