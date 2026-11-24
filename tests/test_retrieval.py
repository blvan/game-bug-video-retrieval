import itertools
import unittest

from scripts.analyze_retrieval import random_metrics
from scripts.prepare_queries import extract, prepare
from scripts.run_retrieval import METRICS, retrieval_metrics, text_windows

try:
    from scripts.evaluate_robustness import COMPARISONS, evaluate_runs, interval_tables
except ModuleNotFoundError as error:
    if error.name != 'numpy':
        raise
    interval_tables = None


class RetrievalTests(unittest.TestCase):
    def test_recall_counts_fraction_of_multiple_relevant_videos(self):
        metrics = retrieval_metrics(['a', 'c', 'b'], {'a', 'b'})
        self.assertEqual(metrics['recall_at_1'], 0.5)
        self.assertEqual(metrics['hit_at_1'], 1)

    def test_reciprocal_rank_uses_first_relevant_video(self):
        self.assertEqual(retrieval_metrics(['c', 'b', 'a'], {'a', 'b'})['mrr'], 0.5)

    def test_missing_relevant_video_is_rejected(self):
        with self.assertRaises(ValueError):
            retrieval_metrics(['a'], {'b'})

    def test_random_expectations_match_exhaustive_small_rankings(self):
        for size in range(1, 6):
            for count in range(1, size + 1):
                with self.subTest(size=size, relevant=count):
                    relevant = set(range(count))
                    observed = [retrieval_metrics(order, relevant)
                                for order in itertools.permutations(range(size))]
                    expected = random_metrics(size, count)
                    for metric in METRICS:
                        self.assertAlmostEqual(expected[metric],
                                               sum(row[metric] for row in observed) / len(observed))

    def test_chunk_boundaries_preserve_every_content_token(self):
        for size in (0, 1, 74, 75, 76, 150, 151):
            with self.subTest(tokens=size):
                content = list(range(size))
                windows = text_windows(content, 'chunks')
                self.assertEqual(list(itertools.chain.from_iterable(windows)), content)
                self.assertTrue(windows)
                self.assertTrue(all(len(window) <= 75 for window in windows))

    def test_truncation_keeps_only_first_content_window(self):
        self.assertEqual(text_windows(list(range(100)), 'truncate'), [list(range(75))])


class QueryPreparationTests(unittest.TestCase):
    def test_system_section_is_removed_while_symptom_survives(self):
        cleaned, sections = extract('### Game and System Information\nCPU secret\n'
                                    '### Description of the bug\nRider disappears.\n')
        self.assertEqual(cleaned, 'Rider disappears.')
        self.assertEqual(sections['problem'], 'Rider disappears.')

    def test_media_address_is_removed_without_losing_surrounding_symptom(self):
        cleaned, _ = extract('Sprite flickers. [recording.mp4](https://example.org/a.mp4)')
        self.assertEqual(cleaned, 'Sprite flickers.')

    def test_conflicting_issue_snapshots_are_rejected(self):
        row = dict(issue_url='https://github.com/game/game/issues/1', repository='game/game',
                   issue_title='Flicker', issue_body='One symptom', candidate_id='a')
        with self.assertRaisesRegex(ValueError, 'Conflicting source snapshots'):
            prepare([row, dict(row, candidate_id='b', issue_body='Different symptom')])

    def test_same_issue_groups_all_relevant_recordings_once(self):
        row = dict(issue_url='https://github.com/game/game/issues/1', repository='game/game',
                   issue_title='Flicker', issue_body='### Actual behavior\nSprite flickers.', candidate_id='b')
        result, = prepare([row, dict(row, candidate_id='a')])
        self.assertEqual(result['relevant_candidate_ids'], ['a', 'b'])


@unittest.skipIf(interval_tables is None, 'Optional robustness dependency numpy is unavailable')
class RobustnessTests(unittest.TestCase):
    def test_pool_restriction_reranks_retained_shared_relevant_video(self):
        issue = 'https://github.com/game/game/issues/99'
        rankings = [dict(issue_url=issue, variant='title_only', pool='global', rank=str(rank),
                         video_sha256=sha, relevant=str(sha == 'shared'))
                    for rank, sha in enumerate(('excluded-only', 'shared', 'other'), 1)]
        metadata = {(issue, 'title_only', 'global'): dict(repository='game/game', category='rendering')}
        rows = evaluate_runs([('truncate', rankings, metadata)], {'excluded-only'})
        strict, = [r for r in rows if r['subset'].endswith('_and_videos')]
        self.assertEqual(strict['pool_size'], 2)
        self.assertEqual(strict['mrr'], 1)

    def test_paired_bootstrap_is_deterministic_for_same_seed(self):
        conditions = set(itertools.chain.from_iterable(COMPARISONS))
        rows = [dict(subset='full', pool='global', condition=condition, issue_url=issue,
                     **{metric: value for metric in METRICS})
                for condition in sorted(conditions) for issue, value in [('one', 0), ('two', 1)]]
        self.assertEqual(interval_tables(rows, 123, 100), interval_tables(rows, 123, 100))

    def test_identical_paired_conditions_have_zero_difference_interval(self):
        conditions = set(itertools.chain.from_iterable(COMPARISONS))
        rows = [dict(subset='full', pool='global', condition=condition, issue_url=issue,
                     **{metric: value for metric in METRICS})
                for condition in sorted(conditions) for issue, value in [('one', 0), ('two', 1)]]
        _, differences = interval_tables(rows, 123, 100)
        for comparison in differences:
            for interval in comparison['intervals'].values():
                self.assertEqual(interval, dict(mean=0, lower=0, upper=0))


if __name__ == '__main__':
    unittest.main()
