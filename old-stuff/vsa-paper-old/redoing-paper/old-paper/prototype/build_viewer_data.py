"""
Build viewer data: our 500 bare nouns projected onto man/woman/boy/girl axes
using Word2Vec vectors. Includes PCA-reduced vectors for client-side axis changing.

Output: prototype/viewer_data.json with both projections and PCA vectors.
"""
import json
import numpy as np

# ── Load our 500 bare nouns ──
with open('prototype/semantic_topology_large_results.json') as f:
    large = json.load(f)
our_nouns = set()
for item in large['items']:
    if item['category'] == 'bare':
        our_nouns.add(item['label'])

# ── Load Word2Vec ──
with open('prototype/word2vec_10k_labels.tsv', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]
wv_labels = [line.split('\t')[0] for line in lines[1:]]
wv_label_idx = {l: i for i, l in enumerate(wv_labels)}

vectors = np.frombuffer(
    open('prototype/word2vec_10k_tensors.bytes', 'rb').read(),
    dtype=np.float32
).reshape(10000, 200)

# ── Select words: our nouns that exist in Word2Vec + ensure poles ──
poles = ['man', 'woman', 'boy', 'girl']
selected_words = sorted(w for w in our_nouns if w in wv_label_idx)
for p in poles:
    if p not in selected_words:
        selected_words.append(p)
selected_words.sort()

print(f"Selected: {len(selected_words)} words")

# Get vectors for selected words
sel_indices = [wv_label_idx[w] for w in selected_words]
sel_vectors = vectors[sel_indices]

# ── Project onto man/woman/boy/girl axes ──
man_vec = vectors[wv_label_idx['man']]
woman_vec = vectors[wv_label_idx['woman']]
boy_vec = vectors[wv_label_idx['boy']]
girl_vec = vectors[wv_label_idx['girl']]

# Gender axis: man → woman
gender_axis = woman_vec - man_vec
gender_axis = gender_axis / np.linalg.norm(gender_axis)

# Age axis: midpoint(man,woman) → midpoint(boy,girl), orthogonalized
adult_center = (man_vec + woman_vec) / 2
child_center = (boy_vec + girl_vec) / 2
age_raw = child_center - adult_center
age_axis = age_raw - np.dot(age_raw, gender_axis) * gender_axis
age_axis = age_axis / np.linalg.norm(age_axis)

# Center = midpoint of all 4 poles
center = (man_vec + woman_vec + boy_vec + girl_vec) / 4

projections = []
for i, word in enumerate(selected_words):
    centered = sel_vectors[i] - center
    x = float(np.dot(centered, gender_axis))
    y = float(np.dot(centered, age_axis))
    projections.append({
        'l': word,
        'x': round(x, 4),
        'y': round(y, 4)
    })

# ── Verify poles ──
for word in poles + ['king', 'queen', 'father', 'mother']:
    idx = selected_words.index(word) if word in selected_words else -1
    if idx >= 0:
        p = projections[idx]
        print(f"  {word:12s}: gender={p['x']:+.3f}  age={p['y']:+.3f}")

# ── PCA reduction of selected vectors for client-side re-projection ──
# Center the data
mean_vec = sel_vectors.mean(axis=0)
centered = sel_vectors - mean_vec

# SVD-based PCA to 30 dims (enough for custom axes, small file)
U, S, Vt = np.linalg.svd(centered, full_matrices=False)
n_components = 30
pca_vectors = (centered @ Vt[:n_components].T)

# Quantize to reduce size: scale to [-127, 127] range per component
scales = np.abs(pca_vectors).max(axis=0)
scales[scales == 0] = 1
quantized = np.round(pca_vectors / scales * 127).astype(np.int8)

print(f"\nPCA: {sel_vectors.shape} -> {pca_vectors.shape}")
variance_explained = (S[:n_components]**2).sum() / (S**2).sum()
print(f"Variance explained by {n_components} components: {variance_explained:.1%}")

# ── Build output ──
output = {
    'proj': projections,
    'pca': {
        'labels': selected_words,
        'scales': [round(float(s), 6) for s in scales],
        'mean': [round(float(m), 6) for m in mean_vec],
        'basis': [[round(float(v), 6) for v in row] for row in Vt[:n_components]],
        'vectors': quantized.tolist()
    }
}

with open('prototype/viewer_data.json', 'w') as f:
    json.dump(output, f, separators=(',', ':'))

size = len(json.dumps(output, separators=(',', ':')))
print(f"\nOutput: {size/1024:.0f} KB ({size} bytes)")
print(f"  Projections: {len(projections)} points")
print(f"  PCA vectors: {len(selected_words)} × {n_components} (int8 quantized)")
