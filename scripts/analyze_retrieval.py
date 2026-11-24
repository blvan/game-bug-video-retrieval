"""Exact random retrieval expectations and descriptive pilot failure tables."""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
try:
    from scripts.run_retrieval import summarize, write_csv, write_json
except ModuleNotFoundError:
    from run_retrieval import summarize, write_csv, write_json


def random_metrics(size, relevant):
    if not 1 <= relevant <= size:
        raise ValueError('Require 1 <= relevant <= pool size')
    denominator = math.comb(size, relevant)
    def hit(k):
        k = min(k, size)
        return 1 - (math.comb(size - k, relevant) / denominator if size - k >= relevant else 0)
    reciprocal = sum(math.comb(size - rank, relevant - 1) / denominator / rank
                     for rank in range(1, size - relevant + 2))
    return dict(recall_at_1=1 / size, recall_at_5=min(5, size) / size,
                hit_at_1=hit(1), hit_at_5=hit(5), mrr=reciprocal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=Path('data/experiments/clip-pilot'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/experiments/clip-analysis'))
    args = parser.parse_args()
    manifest = json.loads((args.run_dir / 'run_manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('Require completed retrieval run')
    with (args.run_dir / 'per_query.csv').open() as stream:
        queries = list(csv.DictReader(stream))
    with (args.run_dir / 'rankings.csv').open() as stream:
        rankings = list(csv.DictReader(stream))
    grouped = defaultdict(list)
    for row in rankings:
        grouped[(row['issue_url'], row['variant'], row['pool'])].append(row)
    random_rows, seen, failures, variants = [], set(), [], defaultdict(dict)
    for row in queries:
        key = row['issue_url'], row['pool']
        if key not in seen:
            seen.add(key)
            random_rows.append(dict(issue_url=row['issue_url'], repository=row['repository'],
                                    category=row['category'], variant='random_expected', pool=row['pool'],
                                    pool_size=int(row['pool_size']), relevant_files=int(row['relevant_files']),
                                    **random_metrics(int(row['pool_size']), int(row['relevant_files']))))
        if row['pool'] != 'global':
            continue
        ranked = sorted(grouped[(row['issue_url'], row['variant'], 'global')], key=lambda r: int(r['rank']))
        relevant_ranks = [int(r['rank']) for r in ranked if r['relevant'] == 'True']
        variants[row['issue_url']][row['variant']] = dict(first_relevant_rank=min(relevant_ranks), relevant_ranks=relevant_ranks)
        if min(relevant_ranks) > 5:
            failures.append(dict(issue_url=row['issue_url'], variant=row['variant'],
                                 first_relevant_rank=min(relevant_ranks), relevant_ranks=relevant_ranks,
                                 top5=[dict(video_sha256=r['video_sha256'], score=float(r['score'])) for r in ranked[:5]]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / 'random_per_query.csv', random_rows)
    write_json(args.output_dir / 'random_metrics.json', summarize(random_rows))
    write_json(args.output_dir / 'failures.json', failures)
    write_json(args.output_dir / 'variant_ranks.json', [dict(issue_url=k, variants=v) for k,v in variants.items()])
    write_json(args.output_dir / 'analysis_manifest.json', dict(random_policy='Exact uniform random permutations, no sampling',
               random_query_pool_groups=len(random_rows), failed_global_query_conditions=len(failures),
               source_run=str(args.run_dir), limitations=['Exploratory AI-labelled pool', 'Random expectation has no uncertainty interval or significance test']))
    print(json.dumps(dict(random_groups=len(random_rows), failed_conditions=len(failures))))


if __name__ == '__main__':
    main()
