"""
Project Word2Vec 10K embeddings onto man/woman/boy/girl semantic axes.

Gender axis: man → woman direction
Age axis: man → boy direction (adult → young)

The four pole words define a 2D semantic subspace.
All 10K words are projected onto this subspace.
"""
import numpy as np
import json

# ── Load data ──
with open('prototype/word2vec_10k_labels.tsv', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]
labels = [line.split('\t')[0] for line in lines[1:]]  # skip header

vectors = np.frombuffer(
    open('prototype/word2vec_10k_tensors.bytes', 'rb').read(),
    dtype=np.float32
).reshape(10000, 200)

print(f"Loaded {len(labels)} words, {vectors.shape} vectors")

# ── Define axes from poles ──
man_idx = labels.index('man')
woman_idx = labels.index('woman')
boy_idx = labels.index('boy')
girl_idx = labels.index('girl')

man_vec = vectors[man_idx]
woman_vec = vectors[woman_idx]
boy_vec = vectors[boy_idx]
girl_vec = vectors[girl_idx]

# Gender axis: man → woman
gender_axis = woman_vec - man_vec
gender_axis = gender_axis / np.linalg.norm(gender_axis)

# Age axis: orthogonalized
# Raw age direction: midpoint(man,woman) → midpoint(boy,girl)
adult_center = (man_vec + woman_vec) / 2
child_center = (boy_vec + girl_vec) / 2
age_raw = child_center - adult_center

# Gram-Schmidt: remove gender component from age axis
age_axis = age_raw - np.dot(age_raw, gender_axis) * gender_axis
age_axis = age_axis / np.linalg.norm(age_axis)

print(f"Gender axis norm: {np.linalg.norm(woman_vec - man_vec):.3f}")
print(f"Age axis raw norm: {np.linalg.norm(age_raw):.3f}")
print(f"Axes orthogonality: {np.dot(gender_axis, age_axis):.6f} (should be ~0)")

# ── Project all words ──
# Center around the midpoint of all four poles
center = (man_vec + woman_vec + boy_vec + girl_vec) / 4

projections = []
for i in range(len(labels)):
    centered = vectors[i] - center
    x = float(np.dot(centered, gender_axis))   # gender: - = male, + = female
    y = float(np.dot(centered, age_axis))       # age: - = adult, + = young
    projections.append({
        'l': labels[i],
        'x': round(x, 4),
        'y': round(y, 4)
    })

# ── Verify poles ──
for word in ['man', 'woman', 'boy', 'girl', 'king', 'queen', 'prince', 'princess']:
    if word in labels:
        idx = labels.index(word)
        p = projections[idx]
        print(f"  {word:12s}: gender={p['x']:+.3f}  age={p['y']:+.3f}")

# ── Save ──
with open('prototype/word2vec_projected.json', 'w') as f:
    json.dump(projections, f, separators=(',', ':'))

print(f"\nSaved {len(projections)} projected points ({len(json.dumps(projections, separators=(',', ':')))/1024:.0f} KB)")

# ── Stats ──
xs = [p['x'] for p in projections]
ys = [p['y'] for p in projections]
print(f"X range: [{min(xs):.3f}, {max(xs):.3f}]")
print(f"Y range: [{min(ys):.3f}, {max(ys):.3f}]")
