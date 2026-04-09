"""
Reduce Word2Vec 200D vectors via PCA to 50D for client-side custom axis projection.

Outputs a JSON file with:
  - labels: list of word labels
  - vectors: list of 50D vectors (rounded to 4 decimals for compactness)
  - pca_mean: the mean vector (for centering)
"""
import numpy as np
import json

# ── Load data ──
with open('prototype/word2vec_10k_labels.tsv', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]
labels = [line.split('\t')[0] for line in lines[1:]]

vectors = np.frombuffer(
    open('prototype/word2vec_10k_tensors.bytes', 'rb').read(),
    dtype=np.float32
).reshape(10000, 200)

print(f"Loaded {len(labels)} words, {vectors.shape} vectors")

# ── PCA to 50 dimensions ──
n_components = 50
mean = vectors.mean(axis=0)
centered = vectors - mean
cov = np.cov(centered, rowvar=False)
eigenvalues, eigenvectors = np.linalg.eigh(cov)

# Sort by eigenvalue descending
idx = np.argsort(eigenvalues)[::-1]
eigenvectors = eigenvectors[:, idx[:n_components]]

projected = centered @ eigenvectors
variance_explained = eigenvalues[idx[:n_components]].sum() / eigenvalues.sum()
print(f"PCA {vectors.shape[1]}D -> {n_components}D, variance explained: {variance_explained:.1%}")

# ── Also store the PCA transform so we can project pole words back ──
# The client needs: pca_vectors (N x 50), and that's it.
# Axis computation: pick two words, subtract their PCA vectors, normalize = axis direction.
# Then dot product all PCA vectors with axis direction = projection.

# Round for compactness
projected_rounded = np.round(projected, 4)

output = {
    'labels': labels,
    'vectors': projected_rounded.tolist()
}

json_str = json.dumps(output, separators=(',', ':'))
print(f"Output size: {len(json_str) / 1024:.0f} KB")

with open('prototype/word2vec_pca50.json', 'w') as f:
    f.write(json_str)

print(f"Saved to prototype/word2vec_pca50.json")

# ── Verify: project onto man→woman axis and compare with original ──
man_idx = labels.index('man')
woman_idx = labels.index('woman')
boy_idx = labels.index('boy')
girl_idx = labels.index('girl')

gender_axis_pca = projected[woman_idx] - projected[man_idx]
gender_axis_pca = gender_axis_pca / np.linalg.norm(gender_axis_pca)

adult_center = (projected[man_idx] + projected[woman_idx]) / 2
child_center = (projected[boy_idx] + projected[girl_idx]) / 2
age_raw = child_center - adult_center
age_axis_pca = age_raw - np.dot(age_raw, gender_axis_pca) * gender_axis_pca
age_axis_pca = age_axis_pca / np.linalg.norm(age_axis_pca)

center_pca = (projected[man_idx] + projected[woman_idx] + projected[boy_idx] + projected[girl_idx]) / 4

for word in ['man', 'woman', 'boy', 'girl', 'king', 'queen', 'prince', 'princess']:
    if word in labels:
        i = labels.index(word)
        c = projected[i] - center_pca
        x = float(np.dot(c, gender_axis_pca))
        y = float(np.dot(c, age_axis_pca))
        print(f"  {word:12s}: gender={x:+.3f}  age={y:+.3f}")
