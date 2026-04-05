import json
import subprocess
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load competition papers
with open('competition_analysis_raw.json', 'r', encoding='utf-8') as f:
    papers = json.load(f)

print(f"Total papers: {len(papers)}", flush=True)

BASE_URL = "http://18.118.210.52/api/posts/{id}/review"

results = []
reviewed = 0
skipped = 0
errors = 0

for i, paper in enumerate(papers):
    pid = paper['id']
    url = BASE_URL.format(id=pid)

    try:
        # Use curl to fetch, capture output
        result = subprocess.run(
            ['curl', '-s', '-m', '10', url],
            capture_output=True, text=True, encoding='utf-8'
        )
        raw = result.stdout.strip()

        if not raw:
            skipped += 1
            continue

        data = json.loads(raw)

        # Check for 404 / no review
        if 'detail' in data and 'not found' in str(data['detail']).lower():
            skipped += 1
            continue
        if 'review' not in data:
            skipped += 1
            continue

        review = data['review']
        entry = {
            'id': pid,
            'paperId': paper.get('paperId'),
            'title': paper.get('title'),
            'clawName': paper.get('clawName'),
            'category': paper.get('category'),
            'review_rating': review.get('rating'),
            'review_summary': review.get('summary'),
        }
        results.append(entry)
        reviewed += 1

        if (i + 1) % 50 == 0:
            print(f"Progress: {i+1}/{len(papers)} | reviewed: {reviewed} | skipped: {skipped} | errors: {errors}", flush=True)

    except json.JSONDecodeError:
        errors += 1
    except Exception as e:
        errors += 1
        print(f"Error on paper {pid}: {e}", flush=True)

    time.sleep(0.1)

print(f"\nDone! {reviewed} reviews fetched, {skipped} skipped (no review), {errors} errors", flush=True)

with open('competition_reviews.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Saved {len(results)} results to competition_reviews.json", flush=True)
