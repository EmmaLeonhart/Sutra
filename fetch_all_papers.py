import subprocess, json, sys

all_papers = []
page = 1
limit = 100
total = None

while True:
    result = subprocess.run(
        ['curl', '-s', f'http://18.118.210.52/api/posts?page={page}&limit={limit}'],
        capture_output=True
    )
    data = json.loads(result.stdout.decode('utf-8'))
    posts = data.get('posts', [])
    if total is None:
        total = data.get('total', 0)
        print(f'Total papers: {total}', flush=True)

    if not posts:
        print(f'Page {page}: empty, stopping.', flush=True)
        break

    print(f'Page {page}: fetched {len(posts)} posts (cumulative: {len(all_papers) + len(posts)})', flush=True)

    extracted = []
    for p in posts:
        abstract = p.get('abstract') or ''
        extracted.append({
            'id': p.get('id'),
            'paperId': p.get('paperId'),
            'title': p.get('title'),
            'abstract': abstract[:200],
            'clawName': p.get('clawName'),
            'category': p.get('category'),
            'subcategory': p.get('subcategory'),
            'tags': p.get('tags'),
            'upvotes': p.get('upvotes'),
            'downvotes': p.get('downvotes'),
            'createdAt': p.get('createdAt'),
            'version': p.get('version'),
        })
    all_papers.extend(extracted)

    if len(all_papers) >= total:
        print(f'Fetched all {len(all_papers)} papers.', flush=True)
        break

    page += 1

with open(r'C:\Users\Immanuelle\Documents\Github\!Claw4S\competition_analysis_raw.json', 'w', encoding='utf-8') as f:
    json.dump(all_papers, f, indent=2, ensure_ascii=False)

print(f'Saved {len(all_papers)} papers to competition_analysis_raw.json')
