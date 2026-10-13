# From Bug Reports to Gameplay Videos

**Variant B research project:** *From Bug Reports to Gameplay Videos: Evaluating CLIP-Based Retrieval in Open-Source Game Repositories*.

This first version collects **candidate** links between GitHub issues and videos. It does not download videos, verify that an issue is a bug report, check whether a video shows gameplay, or implement CLIP. Those checks are a later manual review step before building the research dataset.

## Requirements

- Python 3.10 or newer
- A GitHub personal access token in `GITHUB_TOKEN` is recommended for higher API limits; public repositories can also be scanned without a token.
- No third-party Python packages (`requirements.txt` is intentionally empty).

## Configure repositories

Copy `repos.example.txt` to `repos.txt` and edit it. Put one public game repository in `owner/name` format on each line. Blank lines and lines beginning with `#` are ignored. The supplied examples are [Endless Sky](https://github.com/endless-sky/endless-sky), [OpenTTD](https://github.com/OpenTTD/OpenTTD), and [The Battle for Wesnoth](https://github.com/wesnoth/wesnoth).

## Run

From the project root, in PowerShell:

```powershell
Copy-Item repos.example.txt repos.txt
$env:GITHUB_TOKEN = "your_token_here"  # optional; do not commit the token
python scripts/collect_candidates.py --repos repos.txt --output-dir data --max-issues-per-repo 100
```

On macOS/Linux, set the optional token with `export GITHUB_TOKEN=...` and run the same `python` command. Use `--max-issues-per-repo 0` to scan all issues. The limit counts issues, excluding pull requests, **per repository**. Issues are read newest first, open and closed. Comments are fetched for each examined issue that has comments.

The script logs the number of issues, comments, and candidate links for each repository and in total. It writes:

- `data/candidates.csv` — one row per video link found in an issue body or comment, including issue text, labels, source text, and URLs.
- `data/candidates.json` — the same rows as JSON.
- `data/summary.json` — collection counts.

The `data/` directory is ignored by Git so raw findings are not published accidentally. If the API returns an error, the script exits without writing a partial result. A GitHub rate-limit error is more likely without a token.

## Matching rules and limitations

The collector recognizes `github.com/user-attachments/assets/...`, URLs ending in `.mp4`, `.webm`, or `.mov` (including URLs with query strings), and YouTube links. It finds links in issue descriptions and issue comments, not in pull requests. A candidate means only that an issue contains a link; it is **not** a validated `bug report ↔ gameplay video` pair. The next research step is to review candidates manually and record inclusion/exclusion decisions.

## Test

```powershell
python -m unittest discover -s tests -v
```

## API references

- [List repository issues](https://docs.github.com/en/rest/issues/issues#list-repository-issues)
- [List issue comments](https://docs.github.com/en/rest/issues/comments#list-issue-comments)
- [Pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
