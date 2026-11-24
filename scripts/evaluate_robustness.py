"""Evaluate post-hoc label sensitivity and paired issue-bootstrap intervals."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from .run_retrieval import METRICS, file_hash, retrieval_metrics, write_csv, write_json
except ImportError:
    from run_retrieval import METRICS, file_hash, retrieval_metrics, write_csv, write_json

EXCLUDED = (
    'https://github.com/CleverRaven/Cataclysm-DDA/issues/65241',
    'https://github.com/azerothcore/azerothcore-wotlk/issues/28192',
)
COMPARISONS = (
    ('truncate/title_structured', 'truncate/title_only'),
    ('truncate/title_cleaned_body', 'truncate/title_only'),
    ('chunks/title_cleaned_body', 'truncate/title_cleaned_body'),
    ('chunks/title_structured', 'truncate/title_structured'),
)


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def bootstrap_summary(values, indices):
    """Rows are issues and columns are metrics, shared resamples pair conditions."""
    samples = values[indices].mean(axis=1)
    lower, upper = np.quantile(samples, [0.025, 0.975], axis=0)
    return {metric: dict(mean=float(values[:, i].mean()), lower=float(lower[i]), upper=float(upper[i]))
            for i, metric in enumerate(METRICS)}


def evaluate_runs(runs, remove_hashes):
    rows = []
    for mode, rankings, metadata in runs:
        grouped = defaultdict(list)
        for row in rankings:
            grouped[(row['issue_url'], row['variant'], row['pool'])].append(row)
        for (issue, variant, pool), ranking in sorted(grouped.items()):
            ranking.sort(key=lambda row: int(row['rank']))
            hashes = [row['video_sha256'] for row in ranking]
            if len(hashes) != len(set(hashes)) or [int(row['rank']) for row in ranking] != list(range(1, len(ranking) + 1)):
                raise ValueError('Duplicate video or noncontiguous ranks')
            relevant = {row['video_sha256'] for row in ranking if row['relevant'] == 'True'}
            meta = metadata[(issue, variant, pool)]
            for subset in ('full', 'sensitivity_excluding_flagged_queries', 'sensitivity_excluding_flagged_queries_and_videos'):
                if subset != 'full' and issue in EXCLUDED:
                    continue
                eligible = hashes
                if subset.endswith('_and_videos'):
                    eligible = [sha for sha in hashes if sha not in remove_hashes]
                rows.append(dict(subset=subset, pool=pool, condition=mode + '/' + variant,
                                 issue_url=issue, repository=meta['repository'], category=meta['category'],
                                 pool_size=len(eligible), relevant_files=len(relevant),
                                 **retrieval_metrics(eligible, relevant)))
    return rows


def interval_tables(rows, seed, repetitions):
    metrics, differences = [], []
    groups = defaultdict(list)
    for row in rows:
        groups[(row['subset'], row['pool'])].append(row)
    rng = np.random.default_rng(seed)
    for (subset, pool), group in sorted(groups.items()):
        issues = sorted({row['issue_url'] for row in group})
        indices = rng.integers(0, len(issues), size=(repetitions, len(issues)))
        conditions = defaultdict(dict)
        for row in group:
            if row['issue_url'] in conditions[row['condition']]:
                raise ValueError('Issue repeated within condition')
            conditions[row['condition']][row['issue_url']] = row
        arrays = {}
        for condition, records in sorted(conditions.items()):
            if set(records) != set(issues):
                raise ValueError('Conditions require identical issue sets')
            values = np.array([[records[issue][metric] for metric in METRICS] for issue in issues])
            arrays[condition] = values
            metrics.append(dict(subset=subset, pool=pool, condition=condition, queries=len(issues),
                                intervals=bootstrap_summary(values, indices)))
        for left, right in COMPARISONS:
            differences.append(dict(subset=subset, pool=pool, comparison=left + ' minus ' + right,
                                    queries=len(issues), intervals=bootstrap_summary(arrays[left] - arrays[right], indices)))
    return metrics, differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=Path('data/experiments/clip-pilot'))
    parser.add_argument('--chunks', type=Path, default=Path('data/experiments/clip-chunks'))
    parser.add_argument('--pairs', type=Path, default=Path('data/validated/validated_pairs.json'))
    parser.add_argument('--media', type=Path, default=Path('data/validated/media_manifest.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/experiments/clip-robustness'))
    parser.add_argument('--seed', type=int, default=20261124)
    parser.add_argument('--repetitions', type=int, default=10000)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    pairs = json.loads(args.pairs.read_text())
    media = json.loads(args.media.read_text())
    by_id = {row['candidate_id']: row for row in media}
    if len(by_id) != len(media):
        raise ValueError('Duplicate candidate IDs')
    excluded_hashes, kept_hashes = set(), set()
    for row in pairs:
        target = excluded_hashes if row['issue_url'] in EXCLUDED else kept_hashes
        target.add(by_id[row['candidate_id']]['sha256'])
    if not set(EXCLUDED).issubset({row['issue_url'] for row in pairs}):
        raise ValueError('Flagged issues absent from dataset')
    remove_hashes = excluded_hashes - kept_hashes
    if args.baseline.resolve() == args.chunks.resolve():
        raise ValueError('Baseline and chunk runs must be different directories')
    policies = {
        'truncate': {'First 75 content tokens with start/end tokens; exploratory truncation baseline',
                     'First 75 content tokens with start/end tokens'},
        'chunks': {'Disjoint 75-content-token windows, exact IDs, max chunk/frame cosine'},
    }
    runs, inputs, manifests = [], [args.pairs, args.media], []
    for mode, path in [('truncate', args.baseline), ('chunks', args.chunks)]:
        manifest_path = path / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        if manifest['status'] != 'complete':
            raise ValueError('Both model runs must be complete')
        # The original truncation manifest predates the explicit text_mode field.
        recorded_mode = manifest.get('text_mode')
        if recorded_mode is None and manifest.get('text_policy') == 'First 75 content tokens with start/end tokens; exploratory truncation baseline':
            recorded_mode = 'truncate'
        if recorded_mode != mode or manifest.get('text_policy') not in policies[mode]:
            raise ValueError('Saved run has an unexpected text mode or policy: ' + str(path))
        for supplied in (args.pairs, args.media):
            recorded = [(name, sha) for name, sha in manifest['inputs'].items()
                        if Path(name).name == supplied.name]
            if len(recorded) != 1 or recorded[0][1] != file_hash(supplied):
                raise ValueError('Current input does not match saved run snapshot: ' + str(supplied))
        manifests.append(manifest)
        rank_path, query_path = path / 'rankings.csv', path / 'per_query.csv'
        inputs.extend([manifest_path, rank_path, query_path])
        metadata = {(r['issue_url'], r['variant'], r['pool']): r for r in read_csv(query_path)}
        runs.append((mode, read_csv(rank_path), metadata))
    for field in ('inputs', 'model_state_sha256', 'activation', 'preprocess', 'videos'):
        if manifests[0][field] != manifests[1][field]:
            raise ValueError('Model runs differ in ' + field)
    rows = evaluate_runs(runs, remove_hashes)
    metrics, differences = interval_tables(rows, args.seed, args.repetitions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / 'per_query.csv', rows)
    write_json(args.output_dir / 'metrics.json', metrics)
    write_json(args.output_dir / 'paired_differences.json', differences)
    write_json(args.output_dir / 'manifest.json', dict(
        created_at=datetime.now(timezone.utc).isoformat(), status='complete', seed=args.seed,
        repetitions=args.repetitions, interval='95% percentile paired issue bootstrap, linear quantiles',
        bootstrap_unit='issue; shared indices across all conditions within subset/pool',
        excluded_issue_urls=list(EXCLUDED), removed_video_hashes=sorted(remove_hashes),
        excluded_candidate_ids=[r['candidate_id'] for r in pairs if r['issue_url'] in EXCLUDED],
        inputs={str(p): file_hash(p) for p in inputs}, script_sha256=file_hash(__file__),
        numpy_version=np.__version__,
        limitations=['Post-hoc sensitivity exclusion selected after inspecting failures; not human gold.',
                     'Issue bootstrap assumes independent issues and does not model game-level clustering.',
                     'Intervals are descriptive; no multiple-comparison correction or held-out confirmation.',
                     'Query-only restriction retains the complete video pool; joint restriction changes pool difficulty.']))
    print(json.dumps(dict(query_rows=len(rows), metric_groups=len(metrics), paired_comparisons=len(differences))))


if __name__ == '__main__':
    main()
