import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.collect_candidates import (analyze_issue, repository_record, scan_repository,
                                       export_results, main, discover)
from scripts.github_api import GitHubClient, CollectionPaused, atomic_json


def issue(number, body='', comments=0):
    return {'number': number, 'html_url': f'https://github.com/a/game/issues/{number}',
            'title': 'Collision bug: player stuck', 'body': body, 'comments': comments,
            'labels': [{'name': 'defect'}], 'created_at': '2025-01-01T00:00:00Z', 'closed_at': '2025-01-02T00:00:00Z'}


def repo(name='a/game', **kwargs):
    return {'full_name': name, 'description': 'Open source platformer game', 'license': {'spdx_id': 'MIT'},
            'topics': ['game'], 'has_issues': True, **kwargs}


def state():
    return {'version': 2, 'repositories': {'a/game': repository_record(repo(), 'test')}, 'issues': {},
            'discovery_completed': [], 'directories_completed': [], 'status': 'running',
            'config': {'issue_search': '', 'media_probe': False}}


class StrategyTests(unittest.TestCase):
    def test_comment_only_video_unlabelled_bug_and_closed_at(self):
        data = issue(1, 'Steps to reproduce: walk into a wall', 1)
        data['labels'] = []
        result = analyze_issue('a/game', data, [{'body': 'https://example.org/collision.mp4', 'html_url': 'https://github.com/a/game/issues/1#comment'}])
        row, = result['rows']
        self.assertEqual(row['source_type'], 'comment')
        self.assertTrue(row['bug_evidence'])
        self.assertTrue(row['visual_evidence'])
        self.assertEqual(row['issue_closed_at'], data['closed_at'])
        self.assertEqual(row['manual_valid'], '')

    def test_dedupe_across_body_comments_preserves_sources(self):
        url = 'https://example.org/a.mp4'
        result = analyze_issue('a/game', issue(1, url), [{'body': url}])
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(len(result['rows'][0]['sources']), 2)

    def test_feature_and_terminal_penalties_do_not_delete_candidates(self):
        data = issue(1, 'only shows terminal https://youtu.be/a')
        data.update(title='Feature request', labels=[])
        row, = analyze_issue('a/game', data, [])['rows']
        self.assertLess(row['candidate_score'], 0)
        self.assertFalse(row['bug_evidence'])
        self.assertIn('manual review', row['reason'])

    def test_images_excluded_but_audited(self):
        result = analyze_issue('a/game', issue(1, 'https://github.com/user-attachments/assets/image'), [], lambda _: {'content_type': 'image/png'})
        self.assertEqual(result['rows'], [])
        self.assertEqual(len(result['rejected']), 1)
        self.assertEqual(result['audit']['decision'], 'no_possible_video')

    def test_repository_filters_are_explicit(self):
        self.assertTrue(repository_record(repo(), 'search')['eligible'])
        self.assertFalse(repository_record(repo(description='awesome curated list of games'), 'search')['eligible'])
        self.assertEqual(repository_record(repo(license=None), 'search')['open_source_status'], 'needs_license_review')
        self.assertTrue(repository_record(repo(license=None), 'search')['eligible'])
        self.assertFalse(repository_record(repo(archived=True), 'search')['eligible'])
        engine = repository_record(repo(description='Game engine'), 'search')
        self.assertTrue(engine['eligible'])
        self.assertIn('needs_gameplay_review', engine['scope'])

    def test_pagination_pr_exclusion_limit_growth_and_resume(self):
        calls = []
        class Client:
            def pages(self, path, params):
                calls.append(path)
                if path.endswith('/issues'):
                    yield [{'pull_request': {}, 'number': 99}, issue(1, 'https://youtu.be/a', 1)]
                    yield [issue(2, 'https://example.org/clip.mkv')]
                else:
                    yield [{'body': 'https://streamable.com/a'}]
                    yield [{'body': 'https://vimeo.com/123'}]
        s = state()
        args = SimpleNamespace(max_issues_per_repo=1, issue_search='')
        scan_repository(Client(), s, s['repositories']['a/game'], args, None, lambda: None)
        self.assertEqual(len(s['issues']), 1)
        self.assertEqual(s['repositories']['a/game']['comments_scanned'], 2)
        args.max_issues_per_repo = 0
        scan_repository(Client(), s, s['repositories']['a/game'], args, None, lambda: None)
        self.assertEqual(len(s['issues']), 2)
        self.assertEqual(s['repositories']['a/game']['scan_status'], 'exhausted')
        self.assertEqual(calls.count('/repos/a/game/issues/1/comments'), 1)

    def test_partial_comment_failure_does_not_commit_issue(self):
        class Client:
            def pages(self, path, params):
                if path.endswith('/issues'):
                    yield [issue(1, 'https://youtu.be/a'), issue(2, comments=1)]
                else:
                    yield [{'body': 'https://youtu.be/b'}]
                    raise CollectionPaused('rate limited')
        s = state()
        with self.assertRaises(CollectionPaused):
            scan_repository(Client(), s, s['repositories']['a/game'], SimpleNamespace(max_issues_per_repo=0, issue_search=''), None, lambda: None)
        self.assertEqual(list(s['issues']), ['a/game#1'])

    def test_manual_review_and_uncertainty_counts_survive_export(self):
        s = state()
        s['issues']['a/game#1'] = analyze_issue('a/game', issue(1, 'https://github.com/user-attachments/assets/id'), [])
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            stats = export_results(s, output)
            path = output / 'video_issue_candidates.csv'
            with path.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                fields, rows = reader.fieldnames, list(reader)
            rows[0]['manual_valid'], rows[0]['review_notes'] = 'no', 'actually a screenshot'
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            export_results(s, output)
            self.assertEqual(json.loads((output/'candidates.json').read_text())[0]['manual_valid'], 'no')
            self.assertEqual(stats['video_evidence_pairs'], 0)
            self.assertEqual(stats['likely_visual_bug_video_pairs'], 0)
            self.assertEqual(stats['automatically_validated_pairs'], 0)

    def test_export_counts_pairs_issues_repositories_and_rejections_separately(self):
        s = state()
        s['repositories']['b/game'] = repository_record(repo('b/game'), 'test')
        s['issues'] = {
            'a/game#1': analyze_issue('a/game', issue(1, 'https://youtu.be/a https://example.org/a.mp4'), [{'body': 'https://youtu.be/a'}]),
            'a/game#2': analyze_issue('a/game', issue(2, 'https://github.com/user-attachments/assets/unknown'), []),
            'a/game#3': analyze_issue('a/game', issue(3, 'https://example.org/screenshot.png'), []),
            'b/game#1': analyze_issue('b/game', issue(1), []),
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            stats = export_results(s, output)
            self.assertEqual(stats['issues_scanned'], 4)
            self.assertEqual(stats['comments_scanned'], 1)
            self.assertEqual(stats['issues_containing_media'], 3)
            self.assertEqual(stats['issues_with_possible_video'], 2)
            self.assertEqual(stats['possible_videos'], 3)
            self.assertEqual(stats['video_evidence_pairs'], 2)
            self.assertEqual(stats['uncertain_media_pairs'], 1)
            self.assertEqual(stats['non_video_media_links'], 1)
            self.assertEqual(stats['repositories_with_candidates'], 1)
            self.assertEqual(stats['top_repositories'], [{'repository': 'a/game', 'candidate_pairs': 3, 'candidate_issues': 2}])
            for original, alias in (('issues_scanned', 'issues_examined'), ('comments_scanned', 'comments_examined'), ('possible_videos', 'candidates')):
                self.assertEqual(stats[original], stats[alias])
            self.assertEqual(json.loads((output / 'summary.json').read_text()), stats)
            with (output / 'rejected_candidates.csv').open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 2)

    def test_main_exports_on_pause_and_resumes_completed_issues(self):
        class Client:
            requests = cache_hits = 0
            incomplete_searches = []
            capped_searches = []
            rate_limits = {}
            fail = True
            comment_calls = 0
            def get(self, path):
                return {'data': repo()}
            def pages(self, path, params):
                if path.endswith('/issues'):
                    yield [issue(1, 'https://youtu.be/a'), issue(2, comments=1)]
                else:
                    self.comment_calls += 1
                    if self.fail:
                        raise CollectionPaused('budget')
                    yield [{'body': 'https://example.org/a.mp4'}]
        client = Client()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            seeds = output/'repos.txt'
            seeds.write_text('a/game\n')
            argv = ['--repos', str(seeds), '--output-dir', str(output/'data'), '--no-media-probe', '--max-issues-per-repo', '0']
            with patch('scripts.collect_candidates.GitHubClient', return_value=client):
                self.assertEqual(main(argv), 2)
                stats = json.loads((output/'data/collection_stats.json').read_text())
                self.assertEqual(stats['issues_scanned'], 1)
                self.assertEqual(stats['status'], 'paused')
                client.fail = False
                self.assertEqual(main(argv), 0)
            stats = json.loads((output/'data/collection_stats.json').read_text())
            self.assertEqual(stats['issues_scanned'], 2)
            self.assertEqual(stats['possible_videos'], 2)
            checkpoint = json.loads((output/'data/checkpoint.json').read_text())
            self.assertEqual(checkpoint['issues'], {})
            import sqlite3
            with sqlite3.connect(output/'data/issues.sqlite3') as store:
                self.assertEqual(store.execute('SELECT COUNT(*) FROM issues').fetchone()[0], 2)


class Response:
    def __init__(self, data, link=''):
        self.data = io.BytesIO(json.dumps(data).encode())
        self.headers = {'Link': link}
    def read(self, *args):
        return self.data.read(*args)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class APITests(unittest.TestCase):
    def test_search_object_pagination_cache_and_incomplete_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = GitHubClient(cache_dir=temporary, search_interval=0)
            pages = [Response({'items': [repo()], 'incomplete_results': True, 'total_count': 1100}, '<https://api.github.com/search/repositories?page=2>; rel="next"'),
                     Response({'items': [repo('b/game')], 'total_count': 1100})]
            with patch('scripts.github_api.urlopen', side_effect=pages):
                self.assertEqual(len(list(client.pages('/search/repositories'))), 2)
            with patch('scripts.github_api.urlopen', side_effect=AssertionError('cache miss')):
                self.assertEqual(len(list(client.pages('/search/repositories'))), 2)
            self.assertEqual(client.requests, 2)
            self.assertEqual(client.cache_hits, 2)
            self.assertTrue(client.incomplete_searches)
            self.assertTrue(client.capped_searches)

    def test_long_rate_limit_pauses_and_plain_403_is_not_retried(self):
        client = GitHubClient(max_wait=0)
        error = HTTPError('https://api.github.com/x', 403, 'limit', {'X-RateLimit-Remaining': '0', 'Retry-After': '100'}, io.BytesIO(b'rate limit'))
        with patch('scripts.github_api.urlopen', side_effect=error):
            with self.assertRaises(CollectionPaused):
                client.get('/x')
        error = HTTPError('https://api.github.com/x', 403, 'forbidden', {}, io.BytesIO(b'forbidden'))
        with patch('scripts.github_api.urlopen', side_effect=error):
            with self.assertRaises(HTTPError):
                client.get('/x')

    def test_no_token_leak_via_next_page_and_budget(self):
        client = GitHubClient('secret', request_budget=1)
        with self.assertRaises(ValueError):
            client.get('https://evil.example/issues')
        with patch('scripts.github_api.urlopen', return_value=Response([])):
            client.get('/first')
        with self.assertRaises(CollectionPaused):
            client.get('/second')

    def test_short_rate_wait_retries(self):
        error = HTTPError('https://api.github.com/x', 429, 'limit', {'Retry-After': '0'}, io.BytesIO(b'rate limit'))
        with patch('scripts.github_api.urlopen', side_effect=[error, Response([])]):
            self.assertEqual(GitHubClient().get('/x')['data'], [])


class DiscoveryTests(unittest.TestCase):
    def test_topic_expansion_pagination_and_duplicate_provenance(self):
        class Client:
            def pages(self, path, params):
                self.last_query = params['q']
                if params['per_page'] == 1:
                    yield [repo()]
                else:
                    yield [repo(), repo('b/game')]
                    yield [repo('c/game'), repo('d/game', archived=True)]
        s = state()
        s['repositories'] = {}
        args = SimpleNamespace(per_topic=1, max_repos=3, topics=['game', 'rpg'], keywords=[], min_stars=0, directory=[])
        discover(Client(), s, args, lambda: None)
        self.assertEqual(len(s['repositories']), 4)
        self.assertEqual(sum(r['eligible'] for r in s['repositories'].values()), 3)
        self.assertEqual(len(s['repositories']['a/game']['discovery_sources']), 2)
        self.assertFalse(s['repositories']['d/game']['eligible'])

    def test_curated_markdown_extracts_repo_links(self):
        import base64
        class Client:
            def pages(self, path, params):
                raise AssertionError('Directory should satisfy target before topic search')
            def get(self, path):
                if '/contents/' in path:
                    text = '[game](https://github.com/a/game) [duplicate](https://github.com/a/game/issues)'
                    return {'data': {'encoding': 'base64', 'content': base64.b64encode(text.encode()).decode()}}
                return {'data': repo()}
        s = state()
        s['repositories'] = {}
        args = SimpleNamespace(per_topic=1, max_repos=1, topics=['game'], keywords=[], min_stars=0, directory=['directory/list/README.md'])
        discover(Client(), s, args, lambda: None)
        self.assertEqual(list(s['repositories']), ['a/game'])
        self.assertIn('directory:directory/list/README.md', s['repositories']['a/game']['discovery_sources'])
