import unittest

from scripts.collect_candidates import candidate_rows, classify_video_url, collect, extract_video_links


class ExtractionTests(unittest.TestCase):
    def test_supported_links_and_markdown_punctuation(self):
        body = (
            "[clip](https://github.com/user-attachments/assets/abc-123) "
            "https://example.org/repro.MP4?download=1, "
            "https://youtu.be/xyz. https://example.org/screenshot.png"
        )
        self.assertEqual(
            extract_video_links(body),
            [
                ("https://github.com/user-attachments/assets/abc-123", "github_attachment"),
                ("https://example.org/repro.MP4?download=1", "video_file"),
                ("https://youtu.be/xyz", "youtube"),
            ],
        )

    def test_no_host_spoofing(self):
        self.assertIsNone(classify_video_url("https://youtube.com.evil.example/watch?v=1"))
        self.assertIsNone(classify_video_url("https://example.com/video.mp4.exe"))


class FakeClient:
    def pages(self, path, params=None):
        if path.endswith("/issues"):
            yield [
                {"number": 1, "html_url": "https://github.com/a/b/issues/1", "title": "Bug", "body": "https://youtu.be/a", "labels": [{"name": "bug"}], "comments": 1},
                {"number": 2, "pull_request": {}, "html_url": "https://github.com/a/b/pull/2"},
            ]
        elif path.endswith("/1/comments"):
            yield [{"html_url": "https://github.com/a/b/issues/1#issuecomment-1", "body": "https://example.com/clip.webm"}]
        else:
            raise AssertionError(path)


class CollectionTests(unittest.TestCase):
    def test_issues_comments_and_pr_filter(self):
        rows, totals = collect(FakeClient(), ["a/b"], 10)
        self.assertEqual((totals["issues_examined"], totals["comments_examined"], totals["candidates"]), (1, 1, 2))
        self.assertEqual([row["source_type"] for row in rows], ["issue", "comment"])
        self.assertEqual(rows[0]["issue_labels"], "bug")

    def test_comment_rows_keep_original_issue_body(self):
        issue = {"number": 1, "html_url": "https://github.com/a/b/issues/1", "body": "Original bug description"}
        comment = {"html_url": issue["html_url"] + "#comment", "body": "https://example.org/repro.mp4"}
        row, = candidate_rows("a/b", issue, comment, "comment")
        self.assertEqual(row["issue_body"], "Original bug description")
        self.assertEqual(row["source_body"], comment["body"])
        self.assertEqual(row["source_type"], "comment")


if __name__ == "__main__":
    unittest.main()

