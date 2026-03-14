"""
Mountain Term Collision Mapper
==============================
Maps a large set of semantically related terms (centered on "mountain")
through various hash/encoding functions to find:
  - Collision zones: where distinct terms map to the same bucket
  - Safe ranges: where terms spread out and stay distinguishable

This is an empirical tool for the neurosymbolic paper — exploring how
symbolic representations handle near-synonyms, morphological variants,
and cross-lingual equivalents.
"""

import hashlib
import zlib
import struct
import math
import json
import sys
import io
from collections import defaultdict, Counter
from itertools import combinations

# Windows Unicode fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# =============================================================================
# TERM GENERATION
# =============================================================================

def generate_mountain_terms():
    """
    Generate a massive list of mountain-related terms.
    Categories: canonical names, variants, articles, multilingual,
    morphological, compounds, abbreviations, misspellings, related concepts.
    """
    terms = []

    # --- Canonical mountain names ---
    peaks = [
        "Everest", "K2", "Kangchenjunga", "Lhotse", "Makalu",
        "Cho Oyu", "Dhaulagiri", "Manaslu", "Nanga Parbat", "Annapurna",
        "Denali", "Kilimanjaro", "Elbrus", "Aconcagua", "Vinson",
        "Puncak Jaya", "Mont Blanc", "Matterhorn", "Fuji", "Rainier",
        "McKinley", "Whitney", "Hood", "Shasta", "Baker",
        "Olympus", "Vesuvius", "Etna", "Krakatoa", "Pinatubo",
        "St. Helens", "Mauna Kea", "Mauna Loa", "Cotopaxi", "Chimborazo",
        "Popocatepetl", "Ararat", "Sinai", "Zion", "Tabor",
        "Rushmore", "Fiji", "Kenya", "Elgon", "Cameroon",
        "Snowdon", "Ben Nevis", "Scafell Pike", "Helvellyn", "Kosciuszko",
        "Aoraki", "Cook", "Erebus", "Kirkjufell", "Grossglockner",
        "Zugspitze", "Triglav", "Musala", "Gerlach", "Rysy",
        "Hoverla", "Elbrus", "Kazbek", "Damavand", "Ararat",
    ]

    # --- "Mount X" / "Mt. X" / "Mt X" / "Mountain X" variants ---
    prefixes = ["Mount", "Mt.", "Mt", "Mountain"]
    for peak in peaks:
        terms.append(peak)
        for prefix in prefixes:
            terms.append(f"{prefix} {peak}")

    # --- Article variants ---
    article_bases = [
        "Mountain", "Mount Everest", "Mt. Everest", "K2",
        "Matterhorn", "Mont Blanc", "Kilimanjaro", "Fuji",
        "Denali", "Olympus", "Vesuvius", "Etna", "Rainier",
        "Aconcagua", "Elbrus", "Kangchenjunga", "Annapurna",
    ]
    for base in article_bases:
        terms.append(base)
        terms.append(f"The {base}")
        terms.append(f"the {base}")
        terms.append(f"A {base}")
        terms.append(f"a {base}")
        terms.append(f"THE {base}")

    # --- Case variants ---
    case_bases = [
        "mountain", "Mountain", "MOUNTAIN", "mOUNTAIN", "MoUnTaIn",
        "mount everest", "Mount Everest", "MOUNT EVEREST", "mount Everest",
        "Mount everest", "MOUNT everest", "mount EVEREST",
        "mt everest", "MT EVEREST", "Mt Everest", "MT Everest",
        "mt. everest", "MT. EVEREST", "Mt. Everest", "MT. Everest",
        "k2", "K2", "k 2", "K 2", "K-2",
    ]
    terms.extend(case_bases)

    # --- Multilingual "mountain" ---
    multilingual = {
        # European
        "Berg": "German",
        "Gebirge": "German (range)",
        "Montagne": "French",
        "Mont": "French",
        "Montana": "Spanish",
        "Montaña": "Spanish",
        "Cerro": "Spanish",
        "Sierra": "Spanish (range)",
        "Cordillera": "Spanish (range)",
        "Montagna": "Italian",
        "Monte": "Italian/Spanish/Portuguese",
        "Montanha": "Portuguese",
        "Serra": "Portuguese (range)",
        "Гора": "Russian (gora)",
        "Гори": "Russian plural",
        "Góra": "Polish",
        "Hora": "Czech",
        "Hegy": "Hungarian",
        "Munte": "Romanian",
        "Planina": "Bulgarian/Serbian",
        "Vuori": "Finnish",
        "Fjäll": "Swedish",
        "Fjell": "Norwegian",
        "Bjerg": "Danish",
        "Mynydd": "Welsh",
        "Beinn": "Scottish Gaelic",
        "Sliabh": "Irish",
        # Asian
        "山": "Chinese/Japanese (shan/yama/san)",
        "岳": "Japanese (take/dake)",
        "峰": "Chinese/Japanese (feng/mine)",
        "嶺": "Chinese (ling)",
        "丘": "Chinese/Japanese (qiu/oka)",
        "산": "Korean (san)",
        "ภูเขา": "Thai",
        "núi": "Vietnamese",
        "गिरि": "Sanskrit (giri)",
        "पर्वत": "Hindi/Sanskrit (parvat)",
        "पहाड़": "Hindi (pahaad)",
        "ダグ": "Turkish (dağ) in katakana",
        "Dağ": "Turkish",
        "Dag": "Turkish (ascii)",
        # Other
        "Jabal": "Arabic (جبل)",
        "Har": "Hebrew (הר)",
        "Mlima": "Swahili",
        "Bundok": "Filipino/Tagalog",
        "Gunung": "Malay/Indonesian",
    }
    for word, lang in multilingual.items():
        terms.append(word)
        terms.append(f"{word} (mountain)")

    # --- Romanization variants ---
    romanizations = [
        "Fujisan", "Fuji-san", "Fuji San", "Fujiyama", "Fuji-yama",
        "Chomolungma", "Qomolangma", "Zhumulangma", "Sagarmatha",
        "Sagarmāthā", "Chomolungma", "Everest",
        "Shan", "Yama", "San", "Dake", "Take", "Mine",
        "Gora", "Hora", "Hory",
    ]
    terms.extend(romanizations)

    # --- Morphological variants ---
    morphological = [
        "mountain", "mountains", "mountainous", "mountaineer",
        "mountaineering", "mountainside", "mountaintop", "mountain-top",
        "mountain top", "mountain range", "mountain pass", "mountain peak",
        "mountain chain", "mountain system", "mountain belt",
        "mount", "mounts", "mounted", "mounting", "mountable",
        "peak", "peaks", "peaked", "peaking",
        "summit", "summits", "summited", "summiting",
        "ridge", "ridges", "ridgeline", "ridged",
        "hill", "hills", "hilly", "hillside", "hilltop", "hillock",
        "knoll", "knolls",
        "butte", "buttes",
        "mesa", "mesas",
        "plateau", "plateaus", "plateaux",
        "bluff", "bluffs",
        "cliff", "cliffs",
        "crag", "crags", "craggy",
        "tor", "tors",
        "fell", "fells",
        "pike", "pikes",
        "ben", "bens",
        "munro", "munros",
        "alp", "alps", "alpine", "alpinist", "alpinism",
        "col", "cols",
        "arete", "arête", "aretes",
        "couloir", "couloirs",
        "cirque", "cirques",
        "corrie", "corries",
        "cwm", "cwms",
        "moraine", "moraines",
        "scree", "talus",
        "elevation", "elevations", "elevated",
        "altitude", "altitudes", "altitudinal",
        "height", "heights", "heighten",
        "ascent", "ascents", "ascending",
        "descent", "descents", "descending",
        "slope", "slopes", "sloped", "sloping",
        "incline", "inclines", "inclined",
        "gradient", "gradients",
        "steep", "steepness", "steeply",
        "volcanic", "volcano", "volcanoes", "volcanism",
        "range", "ranges",
        "massif", "massifs",
        "piedmont",
        "foothill", "foothills",
        "highland", "highlands",
        "lowland", "lowlands",
        "upland", "uplands",
        "terrain", "terrains",
        "topography", "topographic",
        "orography", "orographic",
        "orogeny", "orogenic",
    ]
    terms.extend(morphological)

    # --- Compound and phrase variants ---
    compounds = [
        "mountain climbing", "mountain biking", "mountain goat",
        "mountain lion", "mountain dew", "Mountain Dew",
        "mountain rescue", "mountain warfare", "mountain village",
        "mountain stream", "mountain lake", "mountain air",
        "mountain path", "mountain trail", "mountain road",
        "mountain railway", "mountain hut", "mountain refuge",
        "mountain guide", "mountain sickness", "mountain weather",
        "rocky mountain", "Rocky Mountain", "Rocky Mountains",
        "smoky mountain", "Smoky Mountains", "Great Smoky Mountains",
        "blue mountain", "Blue Mountains", "Blue Mountain",
        "white mountain", "White Mountains", "White Mountain",
        "green mountain", "Green Mountains", "Green Mountain",
        "black mountain", "Black Mountains", "Black Mountain",
        "red mountain", "Red Mountain",
        "iron mountain", "Iron Mountain",
        "gold mountain", "Gold Mountain",
        "stone mountain", "Stone Mountain",
        "table mountain", "Table Mountain",
        "sugar loaf", "Sugarloaf", "Sugar Loaf Mountain",
        "bald mountain", "Bald Mountain",
        "lone mountain", "Lone Mountain",
        "twin peaks", "Twin Peaks",
        "three peaks", "Three Peaks",
        "five peaks", "Five Peaks",
    ]
    terms.extend(compounds)

    # --- Abbreviations and informal ---
    informal = [
        "mtn", "Mtn", "MTN", "mtn.", "Mtn.",
        "mt", "Mt", "MT", "mt.", "Mt.",
        "pk", "Pk", "PK", "pk.", "Pk.",
        "hgt", "Hgt", "HGT",
        "elev", "Elev", "ELEV",
        "alt", "Alt", "ALT",
    ]
    terms.extend(informal)

    # --- Common misspellings ---
    misspellings = [
        "montain", "moutain", "mountian", "mountin", "moutnain",
        "mounatin", "mountane", "montaine", "mounten", "mountan",
        "moutntain", "mauntain", "monutain", "mointain",
        "Everst", "Eversest", "Everrest", "Evrest", "Evereset",
        "Killimanjaro", "Kiliminjaro", "Killamanjaro", "Kilimanjarro",
        "Matterhorne", "Matterorn", "Matternhorn",
        "Kangchenjuga", "Kanchenjunga", "Kangchenjungha",
        "Anapurna", "Anaporna", "Annpurna",
        "Denalli", "Dennali", "Danali",
        "Aconcagwa", "Aconagua", "Aconcaua",
    ]
    terms.extend(misspellings)

    # --- Numeric / coded references ---
    numeric = [
        "8849m", "8849 m", "8,849m", "8849 meters",
        "29032ft", "29,032 ft", "29032 feet",
        "8611m", "8611 m", "8,611m",
        "28251ft", "28,251 ft",
        "peak 1", "Peak 1", "Peak I", "Peak One",
        "peak 2", "Peak 2", "Peak II", "Peak Two",
        "P1", "P2", "P3", "P4", "P5",
        "8000er", "8000m peak", "eight-thousander",
        "seven summits", "Seven Summits", "7 summits",
        "14er", "fourteener", "Fourteener",
    ]
    terms.extend(numeric)

    # --- Historical/mythological mountains ---
    mythological = [
        "Olympus", "Mount Olympus", "Olympus Mons",
        "Sinai", "Mount Sinai", "Horeb",
        "Ararat", "Mount Ararat", "Ağrı Dağı",
        "Meru", "Mount Meru", "Sumeru",
        "Kailash", "Mount Kailash", "Kailāsa",
        "Parnassus", "Mount Parnassus", "Parnassos",
        "Ida", "Mount Ida",
        "Pelion", "Mount Pelion",
        "Ossa", "Mount Ossa",
        "Zion", "Mount Zion",
        "Moriah", "Mount Moriah",
        "Carmel", "Mount Carmel",
        "Tabor", "Mount Tabor",
        "Nebo", "Mount Nebo",
        "Calvary", "Mount Calvary", "Golgotha",
        "Penglai", "Kunlun", "Kunlun Mountains",
        "Sumeru", "Mount Sumeru",
        "Mandara", "Mount Mandara",
        "Qaf", "Mount Qaf",
    ]
    terms.extend(mythological)

    # --- Fictional mountains ---
    fictional = [
        "Erebor", "Lonely Mountain", "The Lonely Mountain",
        "Mount Doom", "Orodruin", "Amon Amarth",
        "Caradhras", "Redhorn",
        "Misty Mountains", "The Misty Mountains",
        "Iron Hills",
        "Thangorodrim",
        "Mount Crumpit",
        "Bald Mountain",
        "Candy Mountain",
    ]
    terms.extend(fictional)

    # --- Deduplicate while preserving order ---
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique


# =============================================================================
# HASH / ENCODING FUNCTIONS
# =============================================================================

def hash_md5_16bit(term):
    """MD5 truncated to 16-bit range (0-65535)."""
    h = hashlib.md5(term.encode("utf-8")).digest()
    return struct.unpack("<H", h[:2])[0]

def hash_md5_12bit(term):
    """MD5 truncated to 12-bit range (0-4095)."""
    return hash_md5_16bit(term) & 0xFFF

def hash_md5_8bit(term):
    """MD5 truncated to 8-bit range (0-255)."""
    return hash_md5_16bit(term) & 0xFF

def hash_sha256_16bit(term):
    """SHA-256 truncated to 16 bits."""
    h = hashlib.sha256(term.encode("utf-8")).digest()
    return struct.unpack("<H", h[:2])[0]

def hash_crc32(term):
    """CRC32, full 32-bit."""
    return zlib.crc32(term.encode("utf-8")) & 0xFFFFFFFF

def hash_crc32_16bit(term):
    """CRC32 truncated to 16 bits."""
    return hash_crc32(term) & 0xFFFF

def hash_crc32_12bit(term):
    """CRC32 truncated to 12 bits."""
    return hash_crc32(term) & 0xFFF

def hash_crc32_8bit(term):
    """CRC32 truncated to 8 bits."""
    return hash_crc32(term) & 0xFF

def hash_djb2(term):
    """DJB2 hash (Dan Bernstein) — common string hash."""
    h = 5381
    for c in term.encode("utf-8"):
        h = ((h << 5) + h + c) & 0xFFFFFFFF
    return h

def hash_djb2_16bit(term):
    return hash_djb2(term) & 0xFFFF

def hash_djb2_12bit(term):
    return hash_djb2(term) & 0xFFF

def hash_djb2_8bit(term):
    return hash_djb2(term) & 0xFF

def hash_fnv1a(term):
    """FNV-1a 32-bit hash."""
    h = 0x811c9dc5
    for b in term.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def hash_fnv1a_16bit(term):
    return hash_fnv1a(term) & 0xFFFF

def hash_fnv1a_12bit(term):
    return hash_fnv1a(term) & 0xFFF

def hash_fnv1a_8bit(term):
    return hash_fnv1a(term) & 0xFF

def hash_sum_mod(term, mod=256):
    """Simple sum of byte values mod N."""
    return sum(term.encode("utf-8")) % mod

def hash_length_mod(term, mod=64):
    """Just the string length mod N. Terrible hash — good for showing collisions."""
    return len(term.encode("utf-8")) % mod

def hash_first_last_byte(term):
    """XOR of first and last byte. Another intentionally weak hash."""
    b = term.encode("utf-8")
    if len(b) == 0:
        return 0
    return (b[0] ^ b[-1]) & 0xFF

def hash_case_insensitive_md5_16bit(term):
    """MD5 of lowercased term — shows how case-folding affects collisions."""
    h = hashlib.md5(term.lower().encode("utf-8")).digest()
    return struct.unpack("<H", h[:2])[0]

def hash_stripped_md5_16bit(term):
    """MD5 after stripping articles, punctuation, spaces, and lowering."""
    import re
    cleaned = re.sub(r"^(the|a|an)\s+", "", term, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned.lower())
    h = hashlib.md5(cleaned.encode("utf-8")).digest()
    return struct.unpack("<H", h[:2])[0]


# =============================================================================
# ANALYSIS
# =============================================================================

HASH_FUNCTIONS = {
    # Cryptographic truncations
    "MD5-16bit":       (hash_md5_16bit, 65536),
    "MD5-12bit":       (hash_md5_12bit, 4096),
    "MD5-8bit":        (hash_md5_8bit, 256),
    "SHA256-16bit":    (hash_sha256_16bit, 65536),
    # CRC32 truncations
    "CRC32-16bit":     (hash_crc32_16bit, 65536),
    "CRC32-12bit":     (hash_crc32_12bit, 4096),
    "CRC32-8bit":      (hash_crc32_8bit, 256),
    # Classic string hashes
    "DJB2-16bit":      (hash_djb2_16bit, 65536),
    "DJB2-12bit":      (hash_djb2_12bit, 4096),
    "DJB2-8bit":       (hash_djb2_8bit, 256),
    "FNV1a-16bit":     (hash_fnv1a_16bit, 65536),
    "FNV1a-12bit":     (hash_fnv1a_12bit, 4096),
    "FNV1a-8bit":      (hash_fnv1a_8bit, 256),
    # Intentionally weak (to show pathological collisions)
    "ByteSum-mod256":  (lambda t: hash_sum_mod(t, 256), 256),
    "Length-mod64":     (lambda t: hash_length_mod(t, 64), 64),
    "FirstLastXOR":    (hash_first_last_byte, 256),
    # Normalization-aware
    "CaseInsensitive-MD5-16bit": (hash_case_insensitive_md5_16bit, 65536),
    "Stripped-MD5-16bit":        (hash_stripped_md5_16bit, 65536),
}


def analyze_collisions(terms, hash_name, hash_fn, hash_range):
    """Compute collision statistics for one hash function."""
    buckets = defaultdict(list)
    for term in terms:
        val = hash_fn(term)
        buckets[val].append(term)

    collisions = {k: v for k, v in buckets.items() if len(v) > 1}
    collision_count = sum(len(v) - 1 for v in collisions.values())
    max_bucket = max(len(v) for v in buckets.values()) if buckets else 0
    occupied = len(buckets)
    load_factor = len(terms) / hash_range

    # Find the densest collision clusters
    worst_buckets = sorted(collisions.items(), key=lambda x: -len(x[1]))[:10]

    # Find empty ranges (gaps between occupied buckets)
    occupied_vals = sorted(buckets.keys())
    gaps = []
    for i in range(1, len(occupied_vals)):
        gap = occupied_vals[i] - occupied_vals[i - 1]
        if gap > 1:
            gaps.append((occupied_vals[i - 1] + 1, occupied_vals[i] - 1, gap - 1))
    gaps.sort(key=lambda x: -x[2])

    return {
        "hash_name": hash_name,
        "hash_range": hash_range,
        "total_terms": len(terms),
        "occupied_buckets": occupied,
        "collision_buckets": len(collisions),
        "total_collisions": collision_count,
        "max_bucket_size": max_bucket,
        "load_factor": load_factor,
        "utilization": occupied / hash_range,
        "collision_rate": collision_count / len(terms),
        "worst_buckets": worst_buckets,
        "largest_gaps": gaps[:10],
    }


def print_report(results):
    """Print a formatted analysis report."""
    print("=" * 80)
    print(f"  HASH: {results['hash_name']}")
    print(f"  Range: 0–{results['hash_range'] - 1}  "
          f"({results['hash_range']} slots)")
    print("=" * 80)
    print(f"  Terms hashed:       {results['total_terms']}")
    print(f"  Occupied buckets:   {results['occupied_buckets']} / "
          f"{results['hash_range']}  "
          f"({results['utilization']:.1%} utilization)")
    print(f"  Load factor:        {results['load_factor']:.4f}")
    print(f"  Collision buckets:  {results['collision_buckets']}")
    print(f"  Total collisions:   {results['total_collisions']}  "
          f"({results['collision_rate']:.1%} of terms)")
    print(f"  Worst bucket size:  {results['max_bucket_size']}")
    print()

    if results["worst_buckets"]:
        print("  WORST COLLISION CLUSTERS:")
        for val, terms_in_bucket in results["worst_buckets"][:5]:
            print(f"    Bucket {val} ({len(terms_in_bucket)} terms):")
            for t in terms_in_bucket[:8]:
                print(f"      - {repr(t)}")
            if len(terms_in_bucket) > 8:
                print(f"      ... and {len(terms_in_bucket) - 8} more")
        print()

    if results["largest_gaps"]:
        print("  LARGEST EMPTY RANGES (safe zones):")
        for start, end, size in results["largest_gaps"][:5]:
            print(f"    [{start}–{end}]  ({size} empty slots)")
        print()


def pairwise_semantic_analysis(terms):
    """
    Analyze which semantically related pairs collide vs separate
    across hash functions. This is the key insight for the paper:
    do "near" inputs produce "near" or "far" outputs?
    """
    # Define semantic pairs (things that SHOULD be treated as same/similar)
    semantic_pairs = [
        ("Mountain", "mountain"),
        ("Mountain", "MOUNTAIN"),
        ("Mount Everest", "Mt. Everest"),
        ("Mount Everest", "Mt Everest"),
        ("Mount Everest", "Everest"),
        ("Mount Everest", "The Mount Everest"),
        ("Mount Everest", "mount everest"),
        ("Mount Everest", "MOUNT EVEREST"),
        ("Mount Everest", "Chomolungma"),
        ("Mount Everest", "Sagarmatha"),
        ("K2", "k2"),
        ("K2", "K-2"),
        ("K2", "k 2"),
        ("mountain", "Mountain"),
        ("mountain", "mountains"),
        ("mountain", "mountainous"),
        ("mountain", "montain"),  # misspelling
        ("mountain", "Berg"),     # German
        ("mountain", "Montagne"), # French
        ("mountain", "Montaña"),  # Spanish
        ("mountain", "山"),       # CJK
        ("mountain", "산"),       # Korean
        ("mountain", "hill"),     # related but different
        ("mountain", "peak"),     # related but different
        ("mountain", "summit"),   # related but different
        ("Fuji", "Fujisan"),
        ("Fuji", "Fujiyama"),
        ("Fuji", "Mount Fuji"),
        ("Mont Blanc", "Monte Bianco"),
        ("Mount Doom", "Orodruin"),
        ("Lonely Mountain", "Erebor"),
        ("Mount Olympus", "Olympus"),
        ("Mount Olympus", "Olympus Mons"),
    ]

    print("=" * 80)
    print("  PAIRWISE SEMANTIC ANALYSIS")
    print("  Do semantically related terms collide or separate?")
    print("=" * 80)
    print()

    # Test a subset of hash functions
    test_hashes = [
        ("MD5-8bit", hash_md5_8bit, 256),
        ("MD5-12bit", hash_md5_12bit, 4096),
        ("CRC32-8bit", hash_crc32_8bit, 256),
        ("DJB2-8bit", hash_djb2_8bit, 256),
        ("ByteSum-mod256", lambda t: hash_sum_mod(t, 256), 256),
        ("CaseInsensitive-MD5-16bit", hash_case_insensitive_md5_16bit, 65536),
        ("Stripped-MD5-16bit", hash_stripped_md5_16bit, 65536),
    ]

    for hash_name, hash_fn, hash_range in test_hashes:
        collisions = []
        distances = []
        for a, b in semantic_pairs:
            va = hash_fn(a)
            vb = hash_fn(b)
            dist = abs(va - vb)
            # Wrap-around distance
            wrap_dist = min(dist, hash_range - dist)
            distances.append((a, b, va, vb, wrap_dist))
            if va == vb:
                collisions.append((a, b, va))

        print(f"  {hash_name} (range {hash_range}):")
        print(f"    Collisions among semantic pairs: {len(collisions)} / {len(semantic_pairs)}")
        if collisions:
            for a, b, v in collisions[:5]:
                print(f"      COLLISION: {repr(a)} == {repr(b)} → {v}")
        avg_dist = sum(d[4] for d in distances) / len(distances)
        print(f"    Avg distance between semantic pairs: {avg_dist:.1f} / {hash_range}")
        print(f"    Distance ratio: {avg_dist / hash_range:.4f}")

        # Find closest non-colliding pairs
        near_misses = sorted([d for d in distances if d[4] > 0], key=lambda x: x[4])[:3]
        if near_misses:
            print(f"    Nearest non-collisions:")
            for a, b, va, vb, d in near_misses:
                print(f"      {repr(a)}({va}) vs {repr(b)}({vb}): distance {d}")
        print()


def distribution_histogram(terms, hash_fn, hash_range, hash_name, num_bins=32):
    """Show ASCII histogram of hash distribution."""
    values = [hash_fn(t) for t in terms]
    bin_size = hash_range / num_bins
    bins = [0] * num_bins
    for v in values:
        b = min(int(v / bin_size), num_bins - 1)
        bins[b] += 1

    max_count = max(bins) if bins else 1
    bar_width = 50

    print(f"  Distribution: {hash_name}")
    print(f"  {num_bins} bins across range [0, {hash_range})")
    print()
    for i, count in enumerate(bins):
        lo = int(i * bin_size)
        hi = int((i + 1) * bin_size) - 1
        bar_len = int(count / max_count * bar_width) if max_count > 0 else 0
        bar = "█" * bar_len
        label = f"  [{lo:>5}–{hi:>5}]"
        print(f"{label} {bar} {count}")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║           MOUNTAIN TERM COLLISION MAPPER                           ║")
    print("║   Mapping semantic neighborhoods to find collisions & safe zones   ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()

    terms = generate_mountain_terms()
    print(f"Generated {len(terms)} unique mountain-related terms.")
    print()

    # --- Run all hash functions ---
    all_results = []
    for name, (fn, rng) in sorted(HASH_FUNCTIONS.items()):
        result = analyze_collisions(terms, name, fn, rng)
        all_results.append(result)

    # --- Summary table ---
    print("=" * 80)
    print("  SUMMARY: ALL HASH FUNCTIONS")
    print("=" * 80)
    print(f"  {'Hash Function':<30} {'Range':>7} {'Collisions':>11} "
          f"{'Rate':>7} {'MaxBucket':>10} {'Util':>7}")
    print("  " + "-" * 76)
    for r in sorted(all_results, key=lambda x: x["collision_rate"]):
        print(f"  {r['hash_name']:<30} {r['hash_range']:>7} "
              f"{r['total_collisions']:>11} "
              f"{r['collision_rate']:>6.1%} "
              f"{r['max_bucket_size']:>10} "
              f"{r['utilization']:>6.1%}")
    print()

    # --- Detailed reports for interesting ones ---
    interesting = ["MD5-8bit", "DJB2-8bit", "ByteSum-mod256",
                   "Length-mod64", "FirstLastXOR",
                   "CaseInsensitive-MD5-16bit", "Stripped-MD5-16bit"]
    for r in all_results:
        if r["hash_name"] in interesting:
            print_report(r)

    # --- Distribution histograms for select hashes ---
    print("=" * 80)
    print("  DISTRIBUTION HISTOGRAMS")
    print("=" * 80)
    print()
    for name in ["MD5-8bit", "DJB2-8bit", "ByteSum-mod256", "FirstLastXOR"]:
        fn, rng = HASH_FUNCTIONS[name]
        distribution_histogram(terms, fn, rng, name, num_bins=16)

    # --- Pairwise semantic analysis ---
    pairwise_semantic_analysis(terms)

    # --- Export collision data as JSON ---
    export = {}
    for r in all_results:
        export[r["hash_name"]] = {
            "range": r["hash_range"],
            "total_terms": r["total_terms"],
            "collisions": r["total_collisions"],
            "collision_rate": round(r["collision_rate"], 4),
            "max_bucket": r["max_bucket_size"],
            "utilization": round(r["utilization"], 4),
            "worst_buckets": [
                {"value": v, "count": len(ts), "terms": ts[:5]}
                for v, ts in r["worst_buckets"][:5]
            ],
        }

    with open("collision_results.json", "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)
    print("Results exported to collision_results.json")
    print()


if __name__ == "__main__":
    main()
