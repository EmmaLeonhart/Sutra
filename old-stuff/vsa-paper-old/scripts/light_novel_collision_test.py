#!/usr/bin/env python3
"""
Test whether light novel titles collide in embedding space,
and whether those collisions fall in the oversymbolic regime
alongside the diacritic-collapse collisions from the paper.
"""

import json
import numpy as np
import ollama
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'
EMBED_MODEL = 'mxbai-embed-large'
COLLISION_THRESHOLD = 0.95

# Light novel titles - mix of romanized Japanese, English, and hybrid
# These are real titles that stress tokenizers with non-Latin scripts,
# long compound words, and diacritics
LIGHT_NOVEL_TITLES = [
    # Classic isekai / fantasy
    "Sword Art Online",
    "Re:Zero kara Hajimeru Isekai Seikatsu",
    "Tensei shitara Slime Datta Ken",
    "Tate no Yuusha no Nariagari",
    "Mushoku Tensei: Isekai Ittara Honki Dasu",
    "Overlord",
    "No Game No Life",
    "KonoSuba: Kono Subarashii Sekai ni Shukufuku wo!",
    "Youjo Senki: Saga of Tanya the Evil",
    "Log Horizon",
    "Danmachi: Dungeon ni Deai wo Motomeru no wa Machigatteiru Darou ka",
    "Goblin Slayer",
    "Grimgar of Fantasy and Ash",
    "Hai to Gensou no Grimgar",
    "Arifureta Shokugyou de Sekai Saikyou",
    "Death March kara Hajimaru Isekai Kyousoukyoku",
    "Kumo Desu ga, Nani ka?",
    "The Rising of the Shield Hero",
    "Tenken: That Time I Got Reincarnated as a Sword",
    "Tsuki ga Michibiku Isekai Douchuu",

    # Romance / slice of life
    "Toradora!",
    "Oregairu: Yahari Ore no Seishun Love Comedy wa Machigatteiru",
    "Sakurasou no Pet na Kanojo",
    "Boku wa Tomodachi ga Sukunai",
    "Chuunibyou demo Koi ga Shitai!",
    "Saenai Heroine no Sodatekata",
    "Seishun Buta Yarou wa Bunny Girl Senpai no Yume wo Minai",
    "Kaguya-sama wa Kokurasetai",
    "Nisekoi",
    "Oreimo: Ore no Imouto ga Konnani Kawaii Wake ga Nai",

    # Action / sci-fi
    "Toaru Majutsu no Index",
    "Toaru Kagaku no Railgun",
    "Durarara!!",
    "Baccano!",
    "Steins;Gate",
    "Psycho-Pass",
    "Mahouka Koukou no Rettousei",
    "Rakudai Kishi no Cavalry",
    "Gakusen Toshi Asterisk",
    "Chivalry of a Failed Knight",

    # Horror / dark
    "Another",
    "Boogiepop wa Warawanai",
    "Shin Sekai Yori",
    "Higurashi no Naku Koro ni",
    "Umineko no Naku Koro ni",

    # Modern popular
    "86: Eighty-Six",
    "Spy x Family",
    "Oshi no Ko",
    "Jujutsu Kaisen",
    "Kimetsu no Yaiba",
    "Chainsaw Man",
    "Bocchi the Rock!",
    "Sono Bisque Doll wa Koi wo Suru",
    "Isekai Ojisan",
    "Tensura Nikki: Tensei shitara Slime Datta Ken",

    # Titles with special characters / long romanized phrases
    "Mondaiji-tachi ga Isekai kara Kuru Sou Desu yo?",
    "Seirei Gensouki: Spirit Chronicles",
    "Sōsō no Frieren",
    "Mahō Tsukai no Yome",
    "Kōtetsujō no Kabaneri",
    "Shingeki no Kyojin",
    "Jōkamachi no Dandelion",
    "Kūchū Buranko",
    "Tōkyō Ghoul",
    "Shōjo Kageki Revue Starlight",
    "Kōdo Giasu: Hangyaku no Rurūshu",
    "Yū Yū Hakusho",
    "Rurouni Kenshin: Meiji Kenkaku Romantan",
    "Natsume Yūjinchō",
    "Gintama",
    "Bōsō Shōjo",

    # Very long descriptive titles (LN trademark)
    "Watashi, Nouryoku wa Heikinchi de tte Itta yo ne!",
    "Otome Game no Hametsu Flag shika Nai Akuyaku Reijou ni Tensei shiteshimatta",
    "Watashi no Shiawase na Kekkon",
    "Ryuugajou Nanana no Maizoukin",
    "Netoge no Yome wa Onnanoko ja Nai to Omotta?",
    "Hige wo Soru. Soshite Joshikousei wo Hirou.",
    "Kanojo, Okarishimasu",
    "Komi-san wa, Comyushou desu.",
    "Uzaki-chan wa Asobitai!",

    # Titles with macrons/diacritics that should stress WordPiece
    "Sōsō no Frieren",
    "Jūjutsu Kaisen",
    "Tōkyō Revengers",
    "Shūmatsu Nani Shitemasu ka? Isogashii Desu ka? Sukutte Moratte Ii Desu ka?",
    "Fūka",
    "Kōkaku Kidōtai",
    "Mahōka Kōkō no Rettōsei",
    "Nōgēmu Nōraifu",
    "Dēmon Sureyā",
    "Kūbo Ibuki",
]


def embed_texts(texts):
    """Embed texts via Ollama mxbai-embed-large."""
    result = ollama.embed(model=EMBED_MODEL, input=texts)
    return np.array([np.array(e) for e in result.embeddings])


def load_existing_data():
    """Load the existing embedding space from the paper."""
    emb = np.load(str(DATA_DIR / 'embeddings.npz'))['vectors']
    with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
        index = json.load(f)
    return emb, index


def cosine_sim_matrix(a, b):
    """Compute cosine similarity matrix between two sets of vectors."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


def knn_distances(emb, k=10):
    """Compute k-NN cosine distances for each vector."""
    normed = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-10)
    distances = []
    batch_size = 1000
    for i in range(0, len(normed), batch_size):
        batch = normed[i:i+batch_size]
        sims = batch @ normed.T
        for j in range(len(batch)):
            row = sims[j]
            # Exclude self
            row_sorted = np.sort(row)[::-1]
            kth_sim = row_sorted[k]  # k-th nearest (0-indexed, skip self at 0)
            distances.append(1.0 - kth_sim)
    return np.array(distances)


def main():
    # Deduplicate titles
    titles = list(dict.fromkeys(LIGHT_NOVEL_TITLES))
    print(f"=== Light Novel Collision Test ===")
    print(f"Titles to test: {len(titles)}")
    print()

    # Step 1: Embed all light novel titles
    print("Embedding light novel titles...")
    ln_embeddings = embed_texts(titles)
    print(f"  Got {ln_embeddings.shape[0]} embeddings, dim={ln_embeddings.shape[1]}")

    # Step 2: Load existing embedding space
    print("Loading existing embedding space...")
    existing_emb, existing_index = load_existing_data()
    print(f"  Existing: {existing_emb.shape[0]} embeddings")

    # Step 3: Check collisions AMONG light novel titles
    print("\n--- Collisions among light novel titles ---")
    ln_sims = cosine_sim_matrix(ln_embeddings, ln_embeddings)
    ln_collisions = []
    for i in range(len(titles)):
        for j in range(i+1, len(titles)):
            if ln_sims[i, j] >= COLLISION_THRESHOLD:
                ln_collisions.append((i, j, ln_sims[i, j]))

    print(f"Collisions (cosine >= {COLLISION_THRESHOLD}): {len(ln_collisions)}")
    for i, j, sim in sorted(ln_collisions, key=lambda x: -x[2]):
        print(f"  {sim:.4f}: '{titles[i]}' <-> '{titles[j]}'")

    # Also show near-misses (0.90-0.95)
    near_misses = []
    for i in range(len(titles)):
        for j in range(i+1, len(titles)):
            if 0.90 <= ln_sims[i, j] < COLLISION_THRESHOLD:
                near_misses.append((i, j, ln_sims[i, j]))
    print(f"\nNear-misses (0.90-0.95): {len(near_misses)}")
    for i, j, sim in sorted(near_misses, key=lambda x: -x[2])[:20]:
        print(f"  {sim:.4f}: '{titles[i]}' <-> '{titles[j]}'")

    # Step 4: Check collisions with EXISTING embedding space
    print("\n--- Collisions with existing Wikidata embeddings ---")
    cross_sims = cosine_sim_matrix(ln_embeddings, existing_emb)
    cross_collisions = []
    for i in range(len(titles)):
        top_idx = np.argmax(cross_sims[i])
        top_sim = cross_sims[i, top_idx]
        if top_sim >= COLLISION_THRESHOLD:
            cross_collisions.append((i, top_idx, top_sim))

    print(f"LN titles colliding with existing embeddings: {len(cross_collisions)}")
    for i, j, sim in sorted(cross_collisions, key=lambda x: -x[2]):
        print(f"  {sim:.4f}: '{titles[i]}' <-> '{existing_index[j]['text']}' ({existing_index[j]['qid']})")

    # Show top nearest neighbors even if below threshold
    print(f"\nTop 20 nearest existing neighbors (any similarity):")
    for i in range(len(titles)):
        top_idx = np.argmax(cross_sims[i])
        top_sim = cross_sims[i, top_idx]
        if top_sim >= 0.85:
            print(f"  {top_sim:.4f}: '{titles[i]}' <-> '{existing_index[top_idx]['text']}' ({existing_index[top_idx]['qid']})")

    # Step 5: Density regime analysis
    print("\n--- Density regime analysis ---")
    # Compute kNN distances for existing space
    print("Computing kNN distances for existing space (this may take a moment)...")
    existing_knn = knn_distances(existing_emb, k=10)
    p25 = np.percentile(existing_knn, 25)
    p75 = np.percentile(existing_knn, 75)
    print(f"  Regime thresholds: oversymbolic <= {p25:.4f}, undersymbolic > {p75:.4f}")

    # Now compute where LN titles fall in the existing space
    # For each LN title, find its k nearest neighbors in the EXISTING space
    print("Computing where LN titles fall in existing density landscape...")
    ln_normed = ln_embeddings / (np.linalg.norm(ln_embeddings, axis=1, keepdims=True) + 1e-10)
    ex_normed = existing_emb / (np.linalg.norm(existing_emb, axis=1, keepdims=True) + 1e-10)

    ln_knn_in_existing = []
    for i in range(len(titles)):
        sims = ln_normed[i] @ ex_normed.T
        top_k = np.sort(sims)[::-1][:10]
        knn_dist = 1.0 - top_k[-1]  # 10th nearest neighbor distance
        ln_knn_in_existing.append(knn_dist)

    ln_knn_in_existing = np.array(ln_knn_in_existing)

    oversymbolic = [i for i in range(len(titles)) if ln_knn_in_existing[i] <= p25]
    isosymbolic = [i for i in range(len(titles)) if p25 < ln_knn_in_existing[i] <= p75]
    undersymbolic = [i for i in range(len(titles)) if ln_knn_in_existing[i] > p75]

    print(f"\nRegime distribution of LN titles in existing space:")
    print(f"  Oversymbolic (dense):  {len(oversymbolic)} ({100*len(oversymbolic)/len(titles):.1f}%)")
    print(f"  Isosymbolic (medium):  {len(isosymbolic)} ({100*len(isosymbolic)/len(titles):.1f}%)")
    print(f"  Undersymbolic (sparse): {len(undersymbolic)} ({100*len(undersymbolic)/len(titles):.1f}%)")

    # Compare: what fraction of EXISTING collisions are oversymbolic?
    existing_oversymbolic_count = sum(1 for d in existing_knn if d <= p25)
    print(f"\n  (For reference: existing space is 25%/50%/25% by definition)")
    print(f"  If LN titles cluster in oversymbolic, they're in the same dense regions as diacritic collisions)")

    # Show which titles fall in each regime
    if oversymbolic:
        print(f"\n  Oversymbolic LN titles ({len(oversymbolic)}):")
        for i in oversymbolic:
            nn_sim = 1.0 - ln_knn_in_existing[i]
            print(f"    kNN_dist={ln_knn_in_existing[i]:.4f}: '{titles[i]}'")

    if undersymbolic:
        print(f"\n  Undersymbolic LN titles ({len(undersymbolic)}):")
        for i in undersymbolic:
            print(f"    kNN_dist={ln_knn_in_existing[i]:.4f}: '{titles[i]}'")

    # Step 6: Diacritic pair test - do macron variants collide with non-macron?
    print("\n--- Diacritic stripping test ---")
    diacritic_pairs = [
        ("Tōkyō Ghoul", "Tokyo Ghoul"),
        ("Jūjutsu Kaisen", "Jujutsu Kaisen"),
        ("Sōsō no Frieren", "Sousou no Frieren"),
        ("Mahōka Kōkō no Rettōsei", "Mahouka Koukou no Rettousei"),
        ("Nōgēmu Nōraifu", "Nogeemu Noraifu"),
        ("Kōkaku Kidōtai", "Koukaku Kidoutai"),
        ("Kōdo Giasu", "Koudo Giasu"),
        ("Yū Yū Hakusho", "Yuu Yuu Hakusho"),
        ("Rūrushu", "Rurushu"),
        ("Shūmatsu", "Shuumatsu"),
        ("Fūka", "Fuuka"),
    ]

    all_diacritic_texts = []
    for a, b in diacritic_pairs:
        all_diacritic_texts.extend([a, b])

    diac_emb = embed_texts(all_diacritic_texts)
    print(f"Testing {len(diacritic_pairs)} macron vs non-macron pairs:")
    for idx, (a, b) in enumerate(diacritic_pairs):
        emb_a = diac_emb[idx * 2]
        emb_b = diac_emb[idx * 2 + 1]
        sim = np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
        marker = " *** COLLISION" if sim >= COLLISION_THRESHOLD else ""
        print(f"  {sim:.4f}: '{a}' <-> '{b}'{marker}")


if __name__ == '__main__':
    main()
