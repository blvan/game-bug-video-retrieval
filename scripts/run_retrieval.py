"""Run an exploratory CLIP retrieval evaluation over the reviewed dataset."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

VARIANTS = ('title_only', 'title_cleaned_body', 'title_structured')
METRICS = ('recall_at_1', 'recall_at_5', 'hit_at_1', 'hit_at_5', 'mrr')


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def retrieval_metrics(ranking, relevant):
    if not relevant or not relevant.issubset(set(ranking)):
        raise ValueError('Every query requires relevant files in its pool')
    first = next(i for i, key in enumerate(ranking, 1) if key in relevant)
    return {'recall_at_1': len(set(ranking[:1]) & relevant) / len(relevant),
            'recall_at_5': len(set(ranking[:5]) & relevant) / len(relevant),
            'hit_at_1': int(first == 1), 'hit_at_5': int(first <= 5), 'mrr': 1 / first}


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        for dimension, value in [('all', 'all'), ('repository', row['repository']),
                                 ('category', row['category'])]:
            groups[(row['pool'], row['variant'], dimension, value)].append(row)
    return [dict(pool=pool, variant=variant, dimension=dimension, group=value,
                 queries=len(group), **{m: sum(r[m] for r in group) / len(group) for m in METRICS})
            for (pool, variant, dimension, value), group in sorted(groups.items())]



def text_windows(content_tokens, mode):
    """Keep exact content IDs so chunk boundaries never alter tokenization."""
    if mode == 'truncate':
        return [content_tokens[:75]]
    return [content_tokens[start:start + 75] for start in range(0, len(content_tokens), 75)] or [[]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs', type=Path, default=Path('data/validated/validated_pairs.json'))
    parser.add_argument('--media', type=Path, default=Path('data/validated/media_manifest.json'))
    parser.add_argument('--queries', type=Path, default=Path('data/review/rq2-clip-pilot.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/experiments/clip-pilot'))
    parser.add_argument('--cache-dir', type=Path, default=Path('data/experiments/.clip-cache'))
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--model-cache-dir', type=Path, default=Path('data/clip-cache'))
    parser.add_argument('--text-mode', choices=('truncate', 'chunks'), default='truncate')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    if args.threads < 1 or args.batch_size < 1:
        parser.error('threads and batch-size must be positive')
    import torch
    import open_clip
    from PIL import Image

    torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = dict(started_at=datetime.now(timezone.utc).isoformat(), status='running',
                    model='ViT-B-32', pretrained='openai', activation='quick_gelu', device='cpu', context_length=77,
                    text_mode=args.text_mode,
                    text_policy=('First 75 content tokens with start/end tokens' if args.text_mode == 'truncate'
                                 else 'Disjoint 75-content-token windows, exact IDs, max chunk/frame cosine'),
                    scoring_limitation='Maximum scoring can favor longer videos and texts with more chunks',
                    frame_policy='1 fps at integer timestamps starting at zero; max frame cosine',
                    python=platform.python_version(), threads=args.threads,
                    versions={p: importlib.metadata.version(p) for p in ['torch', 'open_clip_torch', 'Pillow']},
                    inputs={str(p): file_hash(p) for p in [args.pairs, args.media, args.queries]},
                    source_hashes={str(p): file_hash(p) for p in [Path(__file__), Path(__file__).with_name('prepare_queries.py')]},
                    videos=[], failures=[])
    manifest_path = args.output_dir / 'run_manifest.json'
    try:
        manifest['ffmpeg_version'] = subprocess.check_output([args.ffmpeg, '-version'], text=True).splitlines()[0]
        pairs = json.loads(args.pairs.read_text())
        media = json.loads(args.media.read_text())
        queries = json.loads(args.queries.read_text())
        by_id = {row['candidate_id']: row for row in pairs}
        media_by_id = {row['candidate_id']: row for row in media}
        if len(by_id) != len(pairs) or len(media_by_id) != len(media) or set(by_id) != set(media_by_id):
            raise ValueError('Pairs and media must have identical unique candidate IDs')
        if len({q['issue_url'] for q in queries}) != len(queries):
            raise ValueError('Queries must contain distinct issues')
        expected = defaultdict(set)
        for row in pairs:
            expected[row['issue_url']].add(row['candidate_id'])
        if set(expected) != {q['issue_url'] for q in queries}:
            raise ValueError('Query issue set differs from accepted pairs')
        for query in queries:
            if set(query['relevant_candidate_ids']) != expected[query['issue_url']]:
                raise ValueError('Incorrect query relevance IDs')
        videos = {}
        for row in media:
            if file_hash(row['path']) != row['sha256']:
                raise ValueError(f"Video hash mismatch: {row['candidate_id']}")
            videos.setdefault(row['sha256'], row)
        model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai', device='cpu', force_quick_gelu=True, cache_dir=str(args.model_cache_dir))
        model.eval()
        weight_hash = hashlib.sha256()
        for name, parameter in model.state_dict().items():
            weight_hash.update(name.encode())
            weight_hash.update(parameter.detach().cpu().contiguous().numpy().tobytes())
        manifest['model_state_sha256'] = weight_hash.hexdigest()
        manifest['preprocess'] = repr(preprocess)
        tokenizer = open_clip.get_tokenizer('ViT-B-32')
        frame_features = {}
        for sha, video in sorted(videos.items()):
            key = hashlib.sha256(json.dumps([sha, manifest['model_state_sha256'], manifest['preprocess'],
                                            manifest['versions'], manifest['ffmpeg_version'], manifest['activation'], 'integer-seek-1fps-v2'], sort_keys=True).encode()).hexdigest()
            cache = args.cache_dir / (key + '.pt')
            if cache.exists():
                saved = torch.load(cache, map_location='cpu', weights_only=True)
            else:
                # Probe using ffmpeg itself, keeping ffprobe an optional system dependency.
                probe = subprocess.run([args.ffmpeg, '-hide_banner', '-i', video['path']], capture_output=True, text=True)
                match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', probe.stderr)
                if not match:
                    raise ValueError(f"Cannot determine duration: {video['path']}")
                hours, minutes, seconds = map(float, match.groups())
                duration = hours * 3600 + minutes * 60 + seconds
                timestamps = list(range(math.ceil(duration)))
                features, batch = [], []
                with tempfile.TemporaryDirectory(prefix='clip-frames-') as folder:
                    for timestamp in timestamps:
                        target = Path(folder) / 'frame.png'
                        target.unlink(missing_ok=True)
                        subprocess.run([args.ffmpeg, '-v', 'error', '-y', '-ss', str(timestamp), '-i', video['path'],
                                        '-frames:v', '1', str(target)], check=True, capture_output=True)
                        if not target.exists():
                            raise ValueError(f'Frame missing at {timestamp}: {video["path"]}')
                        with Image.open(target) as image:
                            batch.append(preprocess(image.convert('RGB')))
                        if len(batch) == args.batch_size or timestamp == timestamps[-1]:
                            with torch.inference_mode():
                                encoded = model.encode_image(torch.stack(batch)).float()
                                features.append(torch.nn.functional.normalize(encoded, dim=-1))
                            batch = []
                    saved = dict(features=torch.cat(features), timestamps=timestamps, duration=duration)
                temporary = cache.with_suffix('.tmp')
                torch.save(saved, temporary)
                temporary.replace(cache)
            frame_features[sha] = saved['features']
            manifest['videos'].append(dict(sha256=sha, duration=saved['duration'], timestamps=saved['timestamps'], cache=str(cache)))
            print(f'Encoded {len(frame_features)}/{len(videos)} videos ({len(saved["timestamps"])} frames)', flush=True)
            write_json(manifest_path, manifest)
        rankings, per_query, token_records = [], [], []
        for query in queries:
            relevant = {media_by_id[cid]['sha256'] for cid in query['relevant_candidate_ids']}
            categories = {by_id[cid]['bug_category'] for cid in query['relevant_candidate_ids']}
            category = next(iter(categories)) if len(categories) == 1 else 'mixed'
            for variant in VARIANTS:
                text = query[variant]
                content_tokens = tokenizer.encode(text)
                chunks = text_windows(content_tokens, args.text_mode)
                count = len(content_tokens) + 2
                retained_content = sum(len(chunk) for chunk in chunks)
                token_records.append(dict(issue_url=query['issue_url'], variant=variant, original_tokens=count,
                                          retained_tokens=retained_content + 2 * len(chunks),
                                          truncated=retained_content < len(content_tokens), text=text,
                                          original_content_tokens=len(content_tokens),
                                          retained_content_tokens=retained_content,
                                          chunk_count=len(chunks), chunk_content_token_ids=chunks))
                tokens = torch.zeros((len(chunks), 77), dtype=torch.long)
                for index, chunk in enumerate(chunks):
                    sequence = [tokenizer.sot_token_id, *chunk, tokenizer.eot_token_id]
                    tokens[index, :len(sequence)] = torch.tensor(sequence, dtype=torch.long)
                with torch.inference_mode():
                    vectors = []
                    for start in range(0, len(chunks), args.batch_size):
                        encoded = model.encode_text(tokens[start:start + args.batch_size]).float()
                        vectors.append(torch.nn.functional.normalize(encoded, dim=-1))
                    vectors = torch.cat(vectors)
                    scores = {sha: float((features @ vectors.T).max()) for sha, features in frame_features.items()}
                for pool in ('global', 'within_repository'):
                    eligible = set(videos) if pool == 'global' else {media_by_id[cid]['sha256'] for cid, row in by_id.items() if row['repository'] == query['repository']}
                    ranking = sorted(eligible, key=lambda sha: (-scores[sha], sha))
                    per_query.append(dict(issue_url=query['issue_url'], repository=query['repository'], category=category,
                                          variant=variant, pool=pool, pool_size=len(ranking), relevant_files=len(relevant),
                                          **retrieval_metrics(ranking, relevant)))
                    for rank, sha in enumerate(ranking, 1):
                        rankings.append(dict(issue_url=query['issue_url'], variant=variant, pool=pool, rank=rank,
                                             video_sha256=sha, score=scores[sha], relevant=sha in relevant))
        write_csv(args.output_dir / 'rankings.csv', rankings)
        write_csv(args.output_dir / 'per_query.csv', per_query)
        write_json(args.output_dir / 'metrics.json', summarize(per_query))
        write_json(args.output_dir / 'text_inputs.json', token_records)
        manifest.update(status='complete', queries=len(queries), unique_videos=len(videos),
                        finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as error:
        manifest.update(status='failed', failures=[str(error)])
        raise
    finally:
        write_json(manifest_path, manifest)


if __name__ == '__main__':
    main()
