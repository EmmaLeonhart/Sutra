import requests
import json
import time

BASE_URL = "http://18.118.210.52/api"

accept_ids = [837, 684, 617, 616, 571, 562, 532, 523, 520, 76]
weak_accept_ids = [852, 843, 838, 810, 708, 703, 575, 394, 383, 380, 8]

all_ids = [(id_, "Accept") for id_ in accept_ids] + [(id_, "Weak Accept") for id_ in weak_accept_ids]

results = []

for post_id, rating_category in all_ids:
    print(f"Fetching post {post_id} ({rating_category})...")

    # Fetch paper content
    try:
        r = requests.get(f"{BASE_URL}/posts/{post_id}", timeout=30)
        r.raise_for_status()
        post_data = r.json()
    except Exception as e:
        print(f"  ERROR fetching post {post_id}: {e}")
        post_data = {}

    time.sleep(0.1)

    # Fetch review
    try:
        r2 = requests.get(f"{BASE_URL}/posts/{post_id}/review", timeout=30)
        r2.raise_for_status()
        review_data = r2.json()
    except Exception as e:
        print(f"  ERROR fetching review for {post_id}: {e}")
        review_data = {}

    time.sleep(0.1)

    # Build result object
    result = {
        "id": post_id,
        "rating_category": rating_category,
        "paperId": post_data.get("paperId") or post_data.get("id"),
        "title": post_data.get("title"),
        "clawName": post_data.get("clawName") or post_data.get("agentName") or post_data.get("author"),
        "category": post_data.get("category") or post_data.get("field"),
        "content": post_data.get("content") or post_data.get("body") or post_data.get("abstract"),
        "post_raw": post_data,
        "review": review_data,
    }

    print(f"  Title: {result['title']}")
    print(f"  Review keys: {list(review_data.keys()) if isinstance(review_data, dict) else type(review_data)}")

    results.append(result)

output_path = r"C:\Users\Immanuelle\Documents\Github\!Claw4S\top_papers_analysis.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nDone! Saved {len(results)} papers to {output_path}")
