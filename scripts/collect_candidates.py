"""Discover open-source game repositories and collect reviewable issue/video candidates."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

if __package__:
    from .github_api import GitHubClient, CollectionPaused, atomic_json
    from .media import classify_video_url, clean_url, detect_media, MediaProbe
else:
    from github_api import GitHubClient, CollectionPaused, atomic_json
    from media import classify_video_url, clean_url, detect_media, MediaProbe

REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
TOPICS = ['game', 'game-engine', 'opensource-game', 'game-development', 'godot', 'unity',
          'unreal-engine', 'roguelike', 'rpg', 'platformer', 'simulation', 'strategy-game', 'fps', 'racing-game']
BUG = re.compile(r'\b(bug|defect|crash(?:es|ed|ing)?|glitch|regression|broken|flicker(?:ing)?|clipping|stuck|collision|unexpected|reproduce|rendering|physics|animation|visual)\b', re.I)
VISUAL = re.compile(r'\b(visual|gameplay|graphics|render(?:ing)?|flicker(?:ing)?|clipping|stuck|collision|physics|animation|texture|sprite|camera|invisible|lighting|screen|movement|terrain|shadow|artifact|wrong color)\b', re.I)
BUG_LABEL = re.compile(r'\b(bug|defect|crash|glitch|regression)\b', re.I)
FEATURE = re.compile(r'\b(feature request|enhancement|proposal|suggestion)\b', re.I)
LOG_ONLY = re.compile(r'\b(only (?:shows? |contains? )?(?:logs?|terminal|console|output)|(?:logs?|terminal|console|output) only)\b', re.I)
FIELDS = ['repository', 'repository_license', 'repository_scope', 'repository_open_source_status', 'issue_number', 'issue_url', 'issue_title', 'issue_body', 'issue_labels',
          'issue_created_at', 'issue_closed_at', 'source_type', 'source_url', 'source_created_at',
          'source_body', 'video_url', 'video_type', 'media_status', 'media_evidence',
          'candidate_score', 'bug_evidence', 'visual_evidence', 'reason', 'sources',
          'manual_valid', 'review_notes']
REVIEW_FIELDS = ['manual_valid', 'review_notes']
REPO_FIELDS = ['repository', 'repository_url', 'description', 'topics', 'license', 'stars',
               'discovery_sources', 'eligible', 'filter_reason', 'scope', 'open_source_status', 'open_issues_count', 'scan_status',
               'issues_scanned', 'comments_scanned', 'candidate_pairs', 'error']
AUDIT_FIELDS = ['repository', 'issue_number', 'issue_url', 'issue_title', 'issue_body',
                'issue_labels', 'issue_created_at', 'issue_closed_at', 'comments_examined',
                'candidate_score', 'decision', 'reason', 'detected_media']


def load_repositories(path: Path) -> list[str]:
    repositories, seen = [], set()
    for line_number, raw_line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        repository = raw_line.split('#', 1)[0].strip()
        if not repository:
            continue
        if not REPO_PATTERN.fullmatch(repository):
            raise ValueError(f'{path}:{line_number}: expected owner/name, got {repository!r}')
        if repository.lower() not in seen:
            repositories.append(repository)
            seen.add(repository.lower())
    if not repositories:
        raise ValueError(f'{path}: no repositories found')
    return repositories


def extract_video_links(body):
    """Compatibility helper: possible attachments stay visible, never imply validity."""
    return [(m['url'], m['video_type']) for m in detect_media(body) if m['media_status'] != 'non_video']


def score_issue(issue, videos):
    labels = ', '.join(label.get('name', '') for label in issue.get('labels', []))
    text = (issue.get('title') or '') + '\n' + (issue.get('body') or '')
    score, reasons = 0, []
    explicit_bug = bool(BUG_LABEL.search(labels))
    bug = explicit_bug or bool(BUG.search(text + '\n' + labels))
    visual = bool(VISUAL.search(text + '\n' + labels))
    if explicit_bug:
        score += 2
        reasons.append('+2 explicit bug label')
    if any(v['video_type'] == 'github_attachment' and v['media_status'] == 'video' for v in videos):
        score += 2
        reasons.append('+2 GitHub attachment with video evidence')
    if re.search(r'steps to reproduce', text, re.I):
        score += 1
        reasons.append('+1 reproduction steps phrase')
    if visual:
        score += 1
        reasons.append('+1 visual/gameplay keywords')
    if 1 <= len(videos) <= 3:
        score += 1
        reasons.append('+1 small number of possible videos')
    if LOG_ONLY.search(text):
        score -= 2
        reasons.append('-2 logs/terminal-only wording')
    # Labels/title are stronger request signals than boilerplate issue templates.
    feature = bool(FEATURE.search((issue.get('title') or '') + '\n' + labels))
    if feature:
        score -= 2
        reasons.append('-2 feature request signal')
    if bug and not explicit_bug:
        reasons.append('bug keyword evidence without explicit bug label')
    if not bug:
        reasons.append('bug status uncertain; manual review required')
    return score, bug, visual, '; '.join(reasons)


def analyze_issue(repository, issue, comments, probe=None):
    sources = [(issue, 'issue')] + [(comment, 'comment') for comment in comments]
    media = {}
    for source, source_type in sources:
        for item in detect_media(source.get('body'), probe):
            occurrence = {'source_type': source_type, 'source_url': source.get('html_url', issue['html_url']),
                          'source_created_at': source.get('created_at', ''), 'source_body': source.get('body') or ''}
            url = item['url']
            if url not in media:
                media[url] = {**item, 'sources': []}
            elif media[url]['media_status'] != 'video' and item['media_status'] == 'video':
                media[url].update(item)
            media[url]['sources'].append(occurrence)
    videos = [m for m in media.values() if m['media_status'] != 'non_video']
    score, bug, visual, reason = score_issue(issue, videos)
    base = {'repository': repository, 'issue_number': issue['number'], 'issue_url': issue['html_url'],
            'issue_title': issue.get('title') or '', 'issue_body': issue.get('body') or '',
            'issue_labels': ', '.join(label.get('name', '') for label in issue.get('labels', [])),
            'issue_created_at': issue.get('created_at') or '', 'issue_closed_at': issue.get('closed_at') or ''}
    rows, rejected = [], []
    for m in media.values():
        row = {**base, **m['sources'][0], 'video_url': m['url'], 'video_type': m['video_type'],
               'media_status': m['media_status'], 'media_evidence': m['evidence'],
               'candidate_score': score, 'bug_evidence': bug, 'visual_evidence': visual,
               'reason': reason + '; ' + m['evidence'], 'sources': m['sources'],
               'manual_valid': '', 'review_notes': ''}
        if m['media_status'] == 'non_video':
            row['reason'] = 'Excluded from video pool: ' + m['evidence']
            rejected.append(row)
        else:
            rows.append(row)
    decision = 'candidate_for_review' if rows else 'no_possible_video'
    audit = {**base, 'comments_examined': len(comments), 'candidate_score': score,
             'decision': decision, 'reason': reason if rows else 'No possible video in issue or comments',
             'detected_media': list(media.values())}
    return {'audit': audit, 'rows': rows, 'rejected': rejected}


def candidate_rows(repository, issue, source, source_type):
    """Historical helper; retain original issue context for comment matches."""
    result = analyze_issue(repository, issue, [source] if source_type == 'comment' else [])
    source_url = source.get('html_url', issue['html_url'])
    for row in result['rows']:
        occurrences = [item for item in row['sources']
                       if item['source_type'] == source_type and item['source_url'] == source_url]
        if occurrences:
            yield {**row, **occurrences[0]}


def collect(client, repositories, max_issues_per_repo):
    rows, totals = [], {'repositories': len(repositories), 'issues_examined': 0, 'comments_examined': 0, 'candidates': 0}
    for repository in repositories:
        examined = 0
        path = f'/repos/{repository}/issues'
        for page in client.pages(path, {'state': 'all', 'sort': 'created', 'direction': 'desc', 'per_page': 100}):
            for issue in page:
                if 'pull_request' in issue:
                    continue
                if max_issues_per_repo and examined >= max_issues_per_repo:
                    break
                comments = []
                if issue.get('comments'):
                    for comment_page in client.pages(f"{path}/{issue['number']}/comments", {'per_page': 100}):
                        comments.extend(comment_page)
                rows.extend(analyze_issue(repository, issue, comments)['rows'])
                examined += 1
                totals['comments_examined'] += len(comments)
            if max_issues_per_repo and examined >= max_issues_per_repo:
                break
        totals['issues_examined'] += examined
    totals['candidates'] = len(rows)
    return rows, totals


def repository_record(repo, source):
    name = repo['full_name']
    description = repo.get('description') or ''
    topics = repo.get('topics') or []
    license_info = repo.get('license') or {}
    license_name = license_info.get('spdx_id') or ''
    haystack = (name + ' ' + description).lower()
    reason = ''
    if repo.get('private') or repo.get('fork') or repo.get('archived') or repo.get('has_issues') is False:
        reason = 'Private/fork/archived/issues disabled'
    elif re.search(r'awesome|tutorial|course|cheats?', name.split('/', 1)[1], re.I) or re.search(r'\b(curated list|list of (?:open.source |popular |free )?games|collection of resources|asset pack|interview questions)\b', haystack):
        reason = 'Likely directory/tutorial/assets/cheat repository'
    elif not (set(topics) & set(TOPICS) or re.search(r'\b(game|games|engine|roguelike|rpg|simulator)\b', haystack)):
        reason = 'No game/software evidence in metadata'
    scope = 'engine_or_tool_needs_gameplay_review' if re.search(r'\b(engine|framework|sdk|editor|plugin|library|toolkit)\b', haystack) else 'game_candidate_needs_review'
    return {'repository': name, 'repository_url': repo.get('html_url', f'https://github.com/{name}'),
            'description': description, 'topics': topics, 'license': license_name, 'stars': repo.get('stargazers_count', 0),
            'discovery_sources': [source], 'eligible': not bool(reason), 'filter_reason': reason,
            'scope': scope, 'open_source_status': 'license_detected' if license_name and license_name != 'NOASSERTION' else 'needs_license_review',
            'open_issues_count': repo.get('open_issues_count', 0),
            'scan_status': 'pending' if not reason else 'filtered',
            'issues_scanned': 0, 'comments_scanned': 0, 'candidate_pairs': 0, 'error': ''}


def remember_repository(state, record):
    key = record['repository'].lower()
    if key in state['repositories']:
        existing = state['repositories'][key]
        existing['discovery_sources'] = sorted(set(existing['discovery_sources'] + record['discovery_sources']))
    else:
        state['repositories'][key] = record


def discover(client, state, args, checkpoint):
    # Small batches per topic prevent one popular topic from consuming the whole pool.
    quota = args.per_topic or math.ceil(args.max_repos / len(args.topics))
    queries = [f'topic:{topic} fork:false archived:false stars:>={args.min_stars}' for topic in args.topics]
    queries += [f'{word} in:name,description fork:false archived:false stars:>={args.min_stars}' for word in args.keywords]
    plans = [(query, quota, query) for query in queries]
    plans += [(query, max(quota, 100), query + ' [expanded]') for query in queries]
    # GitHub-hosted curated Markdown directory support, without executing its content.
    for directory in args.directory:
        if directory in state['directories_completed']:
            continue
        parts = directory.split('/', 2)
        if len(parts) != 3 or not REPO_PATTERN.fullmatch('/'.join(parts[:2])):
            raise ValueError('--directory must be owner/repo/path/to/README.md')
        import base64
        payload = client.get(f'/repos/{parts[0]}/{parts[1]}/contents/{parts[2]}')['data']
        if payload.get('encoding') != 'base64':
            raise ValueError('Directory file must be a small base64 GitHub Contents response')
        text = base64.b64decode(payload['content']).decode('utf-8')
        names = dict.fromkeys(re.findall(r'https://github\.com/([\w.-]+/[\w.-]+)', text))
        for name in names:
            if sum(r['eligible'] for r in state['repositories'].values()) >= args.max_repos:
                break
            if name.lower() in state['repositories']:
                continue
            try:
                repo = client.get(f'/repos/{name}')['data']
                record = repository_record(repo, 'directory:' + directory)
            except HTTPError as error:
                if error.code not in (404, 410, 451):
                    raise
                record = repository_record({'full_name': name, 'has_issues': False}, 'directory:' + directory)
                record['filter_reason'] = f'Directory entry metadata unavailable: HTTP {error.code}'
            remember_repository(state, record)
            checkpoint()
        else:
            state['directories_completed'].append(directory)
        checkpoint()

    for query, query_limit, completion_key in plans:
        if completion_key in state['discovery_completed']:
            continue
        if sum(r['eligible'] for r in state['repositories'].values()) >= args.max_repos:
            break
        seen = 0
        for page in client.pages('/search/repositories', {'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': min(query_limit, 100)}):
            for repo in page:
                remember_repository(state, repository_record(repo, query))
                seen += 1
            checkpoint()
            if seen >= query_limit:
                break
        state['discovery_completed'].append(completion_key)
        checkpoint()


def scan_repository(client, state, record, args, probe, checkpoint):
    repository = record['repository']
    prefix = repository.lower() + '#'
    processed = sum(key.startswith(prefix) for key in state['issues'])
    if record['scan_status'] == 'exhausted' or (args.max_issues_per_repo and processed >= args.max_issues_per_repo):
        return
    record['scan_status'], record['error'] = 'scanning', ''
    checkpoint()
    path = f'/repos/{repository}/issues'
    if args.issue_search:
        issue_path = '/search/issues'
        params = {'q': f'repo:{repository} is:issue {args.issue_search}', 'sort': 'created', 'order': 'desc', 'per_page': 100}
    else:
        issue_path = path
        params = {'state': 'all', 'sort': 'created', 'direction': 'desc', 'per_page': 100}
    for page in client.pages(issue_path, params):
        for issue in page:
            if 'pull_request' in issue:
                continue
            key = prefix + str(issue['number'])
            if key in state['issues']:
                continue
            if args.max_issues_per_repo and processed >= args.max_issues_per_repo:
                record['scan_status'] = 'limited'
                checkpoint()
                return
            comments = []
            if issue.get('comments'):
                for comment_page in client.pages(f"{path}/{issue['number']}/comments", {'per_page': 100}):
                    comments.extend(comment_page)
            # Commit issue only after ALL comment pages and media evidence are processed.
            result = analyze_issue(repository, issue, comments, probe)
            state['issues'][key] = result
            processed += 1
            record['issues_scanned'] += 1
            record['comments_scanned'] += len(comments)
            record['candidate_pairs'] += len(result['rows'])
            checkpoint()
        if args.max_issues_per_repo and processed >= args.max_issues_per_repo:
            record['scan_status'] = 'limited'
            checkpoint()
            return
    record['scan_status'] = 'exhausted'
    checkpoint()


def write_csv(path, rows, fields):
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    temporary.replace(path)


def review_key(row):
    return (row['repository'].lower(), str(row['issue_number']), row['video_url'])


def export_results(state, output_dir, client=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [dict(row) for issue in state['issues'].values() for row in issue['rows']]
    rejected = [dict(row) for issue in state['issues'].values() for row in issue['rejected']]
    for row in rows + rejected:
        metadata = state['repositories'].get(row['repository'].lower(), {})
        row.update(repository_license=metadata.get('license', ''), repository_scope=metadata.get('scope', ''),
                   repository_open_source_status=metadata.get('open_source_status', 'needs_license_review'))
    audits = [issue['audit'] for issue in state['issues'].values()]
    # Preserve the human's decisions on every resume/export; never write them into API cache.
    review_path = output_dir / 'video_issue_candidates.csv'
    if review_path.exists():
        with review_path.open(encoding='utf-8-sig', newline='') as stream:
            reviews = {review_key(row): {field: row.get(field, '') for field in REVIEW_FIELDS} for row in csv.DictReader(stream)}
        for row in rows:
            row.update(reviews.get(review_key(row), {}))
    rows.sort(key=lambda row: (-row['candidate_score'], row['repository'], row['issue_number'], row['video_url']))
    for audit in audits:
        if audit['decision'] == 'no_possible_video' and not audit['detected_media']:
            rejected.append({**audit, 'video_url': '', 'media_status': 'no_media'})
    counts = Counter(row['repository'] for row in rows)
    issue_counts = Counter()
    for repository, number in {(r['repository'], r['issue_number']) for r in rows}:
        issue_counts[repository] += 1
    stats = {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'status': state['status'],
        'stop_reason': state.get('stop_reason', ''), 'collection_config': state['config'],
        'requested_scope': state.get('requested_scope', {}),
        'repositories_discovered': len(state['repositories']),
        'repositories_eligible': sum(r['eligible'] for r in state['repositories'].values()),
        'repositories_needing_license_review': sum(r.get('open_source_status') == 'needs_license_review' for r in state['repositories'].values()),
        'non_video_media_links': sum(len(issue['rejected']) for issue in state['issues'].values()),
        'repositories_scanned': sum(r['scan_status'] in ('scanning', 'limited', 'exhausted', 'error') for r in state['repositories'].values()),
        'repositories_with_completed_issues': sum(r['issues_scanned'] > 0 for r in state['repositories'].values()),
        'repositories_exhausted': sum(r['scan_status'] == 'exhausted' for r in state['repositories'].values()),
        'issues_scanned': len(audits), 'comments_scanned': sum(a['comments_examined'] for a in audits),
        'issues_containing_media': sum(bool(a['detected_media']) for a in audits),
        'issues_with_possible_video': len({(r['repository'], r['issue_number']) for r in rows}),
        'possible_videos': len(rows), 'video_evidence_pairs': sum(r['media_status'] == 'video' for r in rows),
        'uncertain_media_pairs': sum(r['media_status'] == 'possible_video' for r in rows),
        'likely_visual_bug_video_pairs': sum(r['media_status'] == 'video' and r['bug_evidence'] and r['visual_evidence'] and r['candidate_score'] >= 5 for r in rows),
        'repositories_with_candidates': len(counts), 'automatically_validated_pairs': 0,
        'top_repositories': [{'repository': repo, 'candidate_pairs': count, 'candidate_issues': issue_counts[repo]} for repo, count in counts.most_common(20)],
        'api_requests_this_run': client.requests if client else 0,
        'api_cache_hits_this_run': client.cache_hits if client else 0,
        'incomplete_searches': sorted(set(state.get('incomplete_searches', []))),
        'searches_over_1000_results': sorted(set(state.get('capped_searches', []))),
        'rate_limits': client.rate_limits if client else {},
        # Original names preserved for users of the initial summary.json.
        'repositories': len(state['repositories']), 'issues_examined': len(audits),
        'comments_examined': sum(a['comments_examined'] for a in audits), 'candidates': len(rows),
    }
    write_csv(output_dir / 'repositories.csv', state['repositories'].values(), REPO_FIELDS)
    write_csv(output_dir / 'scanned_repositories.csv', [r for r in state['repositories'].values() if r['scan_status'] not in ('pending', 'filtered')], REPO_FIELDS)
    write_csv(review_path, rows, FIELDS)
    write_csv(output_dir / 'rejected_candidates.csv', rejected, FIELDS)
    write_csv(output_dir / 'issue_audit.csv', audits, AUDIT_FIELDS)
    write_csv(output_dir / 'candidates.csv', rows, FIELDS)
    atomic_json(output_dir / 'candidates.json', rows)
    atomic_json(output_dir / 'collection_stats.json', stats)
    atomic_json(output_dir / 'summary.json', stats)
    return stats


def save(rows, totals, output_dir):
    """Legacy export API."""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / 'candidates.csv', rows, FIELDS)
    atomic_json(output_dir / 'candidates.json', rows)
    atomic_json(output_dir / 'summary.json', totals)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repos', type=Path, help='Optional seed list; otherwise discover automatically')
    parser.add_argument('--discover', action='store_true', help='Discover in addition to a seed list')
    parser.add_argument('--discover-only', action='store_true')
    parser.add_argument('--topics', type=lambda s: s.split(','), default=TOPICS)
    parser.add_argument('--keywords', action='append', default=[], help='Additional repository keyword query (repeatable)')
    parser.add_argument('--directory', action='append', default=[], help='GitHub curated Markdown: owner/repo/path')
    parser.add_argument('--max-repos', type=int, default=100, help='Discovery target of eligible repos; all observed results saved')
    parser.add_argument('--per-topic', type=int, default=0, help='Results per query; default distributes target across topics')
    parser.add_argument('--min-stars', type=int, default=20)
    parser.add_argument('--max-scan-repos', type=int, default=0, help='Total repositories to scan; 0 all eligible')
    parser.add_argument('--max-issues-per-repo', type=int, default=100, help='Issues per repo; 0 all (may be expensive)')
    parser.add_argument('--issue-search', default='', help='Optional GitHub issue query suffix; selective, capped at 1000 matches/repo')
    parser.add_argument('--output-dir', type=Path, default=Path('data'))
    parser.add_argument('--cache-dir', type=Path, help='Shared API/media cache; default OUTPUT/.cache')
    parser.add_argument('--max-wait', type=float, default=60, help='Maximum rate-limit wait in seconds; longer waits pause')
    parser.add_argument('--request-budget', type=int, default=0, help='Maximum uncached API attempts this run; 0 unlimited')
    parser.add_argument('--no-media-probe', action='store_true', help='Skip HTTP HEAD media type checks')
    parser.add_argument('--refresh-cache', action='store_true', help='Refetch API pages; completed issues remain checkpointed')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    for option in ('max_repos', 'per_topic', 'min_stars', 'max_scan_repos', 'max_issues_per_repo', 'request_budget', 'max_wait'):
        if getattr(args, option) < 0:
            parser.error(f'--{option.replace("_", "-")} must be nonnegative')
    if args.max_repos == 0 or not args.topics or any(not topic.strip() for topic in args.topics):
        parser.error('--max-repos must be positive and --topics nonempty')
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / 'checkpoint.json'
    config = {'issue_search': args.issue_search, 'media_probe': not args.no_media_probe}
    state = {'version': 2, 'repositories': {}, 'issues': {}, 'discovery_completed': [],
             'directories_completed': [], 'config': config, 'status': 'running', 'stop_reason': ''}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('version') != 2 or state['config'] != config:
            parser.error('Checkpoint uses different search/media settings; choose another --output-dir')
    store_path = output / 'issues.sqlite3'
    if store_path.exists() and not state_path.exists():
        parser.error('Issue store exists without checkpoint.json; restore the checkpoint or use a new output directory')
    if state.get('issue_store') and not store_path.exists():
        parser.error('Issue store is missing; restore it with checkpoint.json before resuming')
    store = sqlite3.connect(store_path)
    store.execute('CREATE TABLE IF NOT EXISTS issues (issue_key TEXT PRIMARY KEY, result TEXT NOT NULL)')
    saved_issue_keys = set()
    for key, payload in store.execute('SELECT issue_key, result FROM issues'):
        state['issues'][key] = json.loads(payload)
        saved_issue_keys.add(key)
    # The issue transaction may precede the metadata checkpoint when interrupted.
    # Reconstruct counters from committed issues so that restart is idempotent.
    for record in state['repositories'].values():
        results = [v for k, v in state['issues'].items() if k.startswith(record['repository'].lower() + '#')]
        record['issues_scanned'] = len(results)
        record['comments_scanned'] = sum(v['audit']['comments_examined'] for v in results)
        record['candidate_pairs'] = sum(len(v['rows']) for v in results)
    state['issue_store'] = 'issues.sqlite3'
    state['status'], state['stop_reason'] = 'running', ''
    state['requested_scope'] = {key: getattr(args, key) for key in ('max_repos', 'max_scan_repos', 'max_issues_per_repo', 'topics', 'keywords', 'directory', 'min_stars', 'per_topic', 'discover_only')}
    cache_root = args.cache_dir or output / '.cache'
    client = GitHubClient(os.getenv('GITHUB_TOKEN'), cache_root / 'api', args.max_wait,
                          args.request_budget, args.refresh_cache)
    probe = None if args.no_media_probe else MediaProbe(cache_root / 'media')

    def checkpoint():
        state['incomplete_searches'] = sorted(set(state.get('incomplete_searches', []) + client.incomplete_searches))
        state['capped_searches'] = sorted(set(state.get('capped_searches', []) + client.capped_searches))
        pending = state['issues'].keys() - saved_issue_keys
        if pending:
            with store:
                store.executemany('INSERT OR REPLACE INTO issues VALUES (?, ?)',
                                  [(key, json.dumps(state['issues'][key], ensure_ascii=False)) for key in pending])
            saved_issue_keys.update(pending)
        # Large issue texts live in SQLite; don't rewrite the entire corpus per issue.
        atomic_json(state_path, {**state, 'issues': {}})

    exit_code = 0
    try:
        if args.repos:
            for repository in load_repositories(args.repos):
                if repository.lower() not in state['repositories']:
                    record = repository_record(client.get(f'/repos/{repository}')['data'], 'seed:' + str(args.repos))
                    remember_repository(state, record)
                    checkpoint()
        if args.discover or args.discover_only or not args.repos:
            discover(client, state, args, checkpoint)
        if not args.discover_only:
            records = sorted([r for r in state['repositories'].values() if r['eligible']],
                             key=lambda r: (r.get('scope', '').startswith('engine'), -r.get('open_issues_count', 0), -r.get('stars', 0), r['repository']))
            if args.max_scan_repos:
                records = records[:args.max_scan_repos]
            for record in records:
                try:
                    scan_repository(client, state, record, args, probe, checkpoint)
                except HTTPError as error:
                    if error.code in (404, 410, 451, 403):
                        record['scan_status'], record['error'] = 'error', f'HTTP {error.code}'
                        checkpoint()
                        logging.warning('%s: %s', record['repository'], record['error'])
                        continue
                    raise
                logging.info('%s: issues=%d comments=%d candidates=%d status=%s', record['repository'], record['issues_scanned'], record['comments_scanned'], record['candidate_pairs'], record['scan_status'])
        state['status'] = 'finished_scope'
    except (CollectionPaused, KeyboardInterrupt) as error:
        state['status'], state['stop_reason'] = 'paused', str(error) or 'Interrupted by user'
        exit_code = 2
        logging.warning('%s', state['stop_reason'])
    except (OSError, ValueError) as error:
        state['status'], state['stop_reason'] = 'error', f'{type(error).__name__}: {error}'
        exit_code = 1
        logging.error('%s', state['stop_reason'])
    finally:
        checkpoint()
        stats = export_results(state, output, client)
        store.close()
        for field in ('repositories_discovered', 'repositories_eligible', 'repositories_scanned', 'issues_scanned', 'comments_scanned', 'issues_containing_media', 'possible_videos', 'likely_visual_bug_video_pairs', 'repositories_with_candidates'):
            logging.info('%s: %s', field.replace('_', ' ').capitalize(), stats[field])
        for repo in stats['top_repositories'][:10]:
            logging.info('TOP %s: %d candidate pairs (%d issues)', repo['repository'], repo['candidate_pairs'], repo['candidate_issues'])
        logging.info('Saved review files in %s; status=%s. Candidates require manual validation.', output.resolve(), state['status'])
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
