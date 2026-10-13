"""Collect issue/video-link candidates from public GitHub game repositories."""

from __future__ import annotations

import argparse
import csv
import html
import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
NEXT_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
FIELDS = [
    "repository", "issue_number", "issue_url", "issue_title", "issue_body",
    "issue_labels", "issue_created_at", "source_type", "source_url",
    "source_created_at", "source_body", "video_url", "video_type",
]


def load_repositories(path: Path) -> list[str]:
    repositories = []
    seen = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        repository = raw_line.split("#", 1)[0].strip()
        if not repository:
            continue
        if not REPO_PATTERN.fullmatch(repository):
            raise ValueError(f"{path}:{line_number}: expected owner/name, got {repository!r}")
        if repository.lower() not in seen:
            repositories.append(repository)
            seen.add(repository.lower())
    if not repositories:
        raise ValueError(f"{path}: no repositories found")
    return repositories


def clean_url(url: str) -> str:
    url = url.rstrip(".,;!?:")
    for closing, opening in ((")", "("), ("]", "["), ("}", "{")):
        while url.endswith(closing) and url.count(closing) > url.count(opening):
            url = url[:-1]
    return url


def classify_video_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host == "github.com" and path.startswith("/user-attachments/assets/"):
        return "github_attachment"
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        return "youtube"
    if any(path.endswith(extension) for extension in VIDEO_EXTENSIONS):
        return "video_file"
    return None


def extract_video_links(body: str | None) -> list[tuple[str, str]]:
    found = []
    seen = set()
    for match in URL_PATTERN.finditer(html.unescape(body or "")):
        url = clean_url(match.group(0))
        video_type = classify_video_url(url)
        if video_type and url not in seen:
            found.append((url, video_type))
            seen.add(url)
    return found


class GitHubClient:
    def __init__(self, token: str | None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "game-bug-video-retrieval/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def pages(self, path: str, params: dict[str, str | int] | None = None):
        url = f"{API_ROOT}{path}"
        if params:
            url += "?" + urlencode(params)
        while url:
            request = Request(url, headers=self.headers)
            with urlopen(request, timeout=30) as response:
                data = json.load(response)
                if not isinstance(data, list):
                    raise ValueError(f"Expected a list from {url}")
                yield data
                link_header = response.headers.get("Link", "")
                next_match = NEXT_PATTERN.search(link_header)
                url = next_match.group(1) if next_match else None


def candidate_rows(repository: str, issue: dict, source: dict, source_type: str):
    labels = [label.get("name", "") for label in issue.get("labels", [])]
    for video_url, video_type in extract_video_links(source.get("body")):
        yield {
            "repository": repository,
            "issue_number": issue["number"],
            "issue_url": issue["html_url"],
            "issue_title": issue.get("title", ""),
            "issue_body": issue.get("body") or "",
            "issue_labels": ", ".join(name for name in labels if name),
            "issue_created_at": issue.get("created_at", ""),
            "source_type": source_type,
            "source_url": source.get("html_url", issue["html_url"]),
            "source_created_at": source.get("created_at", ""),
            "source_body": source.get("body") or "",
            "video_url": video_url,
            "video_type": video_type,
        }


def collect(client: GitHubClient, repositories: list[str], max_issues_per_repo: int):
    rows = []
    totals = {"repositories": len(repositories), "issues_examined": 0, "comments_examined": 0, "candidates": 0}
    for repository in repositories:
        repo_issues = repo_comments = repo_candidates = 0
        owner, name = repository.split("/", 1)
        issue_path = f"/repos/{owner}/{name}/issues"
        issue_pages = client.pages(issue_path, {"state": "all", "sort": "created", "direction": "desc", "per_page": 100})
        for page in issue_pages:
            for issue in page:
                if "pull_request" in issue:
                    continue  # GitHub's issues endpoint also returns pull requests.
                if max_issues_per_repo and repo_issues >= max_issues_per_repo:
                    break
                repo_issues += 1
                issue_rows = list(candidate_rows(repository, issue, issue, "issue"))
                rows.extend(issue_rows)
                repo_candidates += len(issue_rows)
                if issue.get("comments", 0):
                    comment_path = f"{issue_path}/{issue['number']}/comments"
                    for comment_page in client.pages(comment_path, {"per_page": 100}):
                        for comment in comment_page:
                            repo_comments += 1
                            comment_rows = list(candidate_rows(repository, issue, comment, "comment"))
                            rows.extend(comment_rows)
                            repo_candidates += len(comment_rows)
            if max_issues_per_repo and repo_issues >= max_issues_per_repo:
                break
        totals["issues_examined"] += repo_issues
        totals["comments_examined"] += repo_comments
        totals["candidates"] += repo_candidates
        logging.info("%s: issues=%d comments=%d candidates=%d", repository, repo_issues, repo_comments, repo_candidates)
    return rows, totals


def save(rows: list[dict], totals: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "candidates.json").open("w", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, indent=2)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(totals, stream, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", type=Path, default=Path("repos.example.txt"), help="Text file with owner/name on each line")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Directory for candidates.csv, candidates.json and summary.json")
    parser.add_argument("--max-issues-per-repo", type=int, default=100, help="Newest non-PR issues per repository; 0 means all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.max_issues_per_repo < 0:
        parser.error("--max-issues-per-repo must be nonnegative")
    try:
        repositories = load_repositories(args.repos)
        rows, totals = collect(GitHubClient(os.getenv("GITHUB_TOKEN")), repositories, args.max_issues_per_repo)
        save(rows, totals, args.output_dir)
    except (OSError, ValueError, HTTPError, URLError) as error:
        logging.error("Collection failed: %s", error)
        return 1
    logging.info("TOTAL: issues=%d comments=%d candidates=%d", totals["issues_examined"], totals["comments_examined"], totals["candidates"])
    logging.info("Saved results in %s", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

