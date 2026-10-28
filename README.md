# From Bug Reports to Gameplay Videos

**Variant B research project:** *From Bug Reports to Gameplay Videos: Evaluating CLIP-Based Retrieval in Open-Source Game Repositories*.

This collector discovers game repositories and gathers **candidates for manual review** from GitHub issues and all their comments. It does not implement CLIP, download recordings, or establish that a video demonstrates a real gameplay bug. A high score is a review priority, not a ground-truth label.

## Research article and persistent Excel review

The English working article is in [paper/](paper/README.md), using the TUKE FEI EEI 2026 LaTeX template. It preserves the approved RQ1–RQ3, separates collection observations from planned CLIP experiments, and cites initial related work checked with Scite. No retrieval results have been claimed.

For the expanded manual review, use the permanent Excel ledger rather than adding columns to a regenerated CSV. See [the manual review protocol](docs/manual-review.md) for field definitions, the provisional bug codebook, safe updates and recovery:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-review.txt
.venv/bin/python scripts/review_workbook.py sync --run-dir data/pilot --workbook data/review/review.xlsx
```

Close the workbook before syncing. Repeating the same input changes nothing; a new run appends only unseen pairs and repositories, preserving existing review cells and rows. Reviewed decisions belong in this workbook. The original collector remains standard-library-only; `openpyxl` is needed only for the optional Excel command. Export fully reviewed pairs with:

```bash
.venv/bin/python scripts/review_workbook.py export --workbook data/review/review.xlsx --output-dir data/validated
```

The initial ledger is unreviewed, so its validated export has zero rows. Back up `data/review/` separately: the data directory is Git-ignored. Code/template updates do not back up manual work.

## Why the original sample was small

The original `repos.example.txt` contained only three repositories. The smoke test inspected three newest non-PR issues per repository: nine issues, nineteen comments, and three attachment URLs, across two repositories. It did not measure the availability of pairs across GitHub. Comments and pagination already worked, but repository discovery, historical media search, media-type verification, scoring, and resumable progress were missing. Every opaque GitHub attachment was incorrectly treated as video evidence, even though it could be an image.

## Requirements and VS Code

- Python **3.10+**; only the standard library, no installation of packages required.
- Open this project folder in VS Code and run the commands below from its integrated terminal.
- `GITHUB_TOKEN` is optional and read from the process environment. The script does **not** load `.env` files. Do not put a real token in code, commands committed to Git, or CSV files.
- On Linux/macOS the command is usually `python3`; on Windows use `python` or `py -3`.

For Bash, enter an optional token without adding its value to shell history:

```bash
read -rsp 'GitHub token: ' GITHUB_TOKEN; echo
export GITHUB_TOKEN
```

Public collection also works without a token, but GitHub normally allows only 60 REST requests/hour per IP and 10 unauthenticated searches/minute. Authenticated REST requests generally have a 5,000/hour limit and search has its own budget. The client spaces searches, follows `Link` headers, honors rate-limit/reset headers, retries temporary failures, and checkpoints before pausing. See [GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) and [search limits](https://docs.github.com/en/rest/search/search).

## Discover repositories automatically

No seed list is required:

```bash
python3 scripts/collect_candidates.py --discover-only --max-repos 100 --output-dir data/discovery
```

Discovery searches all fourteen topics: game, game-engine, opensource-game, game-development, godot, unity, unreal-engine, roguelike, rpg, platformer, simulation, strategy-game, fps, racing-game. Small batches across topics provide variety; if needed a second pass expands each query. The default minimum is 20 stars; lower it with `--min-stars 0`. Add keyword queries with repeated `--keywords`, or replace topics with `--topics game,roguelike,strategy-game`.

`--max-repos` is a target of eligible metadata matches, not an exact number: the last page can overshoot it, and filtered matches are also saved. Discovery is not a census. Topic overlap, star ranking, missing tags and search limits introduce bias. GitHub Search returns at most 1,000 matches per query; incomplete/capped searches are recorded in statistics. Add narrower topics/keywords for coverage.

Obvious directories, tutorial/cheat repositories, forks, archived/private repositories and repositories with issues disabled are filtered, with reasons retained. A missing/unrecognized license is **not silently discarded**: it is marked `needs_license_review`. Engines/tools are flagged as requiring gameplay review. A detected license or game topic alone does not establish final study eligibility.

Optional curated directory input uses GitHub's Contents API to extract repository links from Markdown:

```bash
python3 scripts/collect_candidates.py --discover-only --directory leereilly/games/README.md --max-repos 200 --output-dir data/directories
```

Explicit directory entries are processed before topic searches and are subject to the same metadata checks and total target. Increase the target to collect more entries; remaining capacity is filled from topics. External webpages are not scraped. Optional manual seeds still work:

```bash
python3 scripts/collect_candidates.py --repos repos.example.txt --discover --max-repos 100 --output-dir data/combined
```

## Collect issues and comments

A bounded initial run:

```bash
python3 scripts/collect_candidates.py --max-repos 100 --max-scan-repos 10 --max-issues-per-repo 100 --output-dir data/pilot
```

Without `--max-scan-repos`, all eligible discovered repositories are scanned. `--max-issues-per-repo 0` scans every non-PR issue, open and closed, following every issue/comment page. The issue limit excludes PRs. All comment pages are processed even for issues without bug labels or videos in the original body. Repositories likely to be games are prioritized over engine/tool candidates, then by open issue activity and stars. Linked PR discussions are not currently fetched.

A targeted historical search is useful for quickly finding examples:

```bash
python3 scripts/collect_candidates.py --topics opensource-game,roguelike,strategy-game,game,racing-game --per-topic 40 --max-repos 100 --max-scan-repos 10 --max-issues-per-repo 10 --issue-search 'mp4 in:body,comments' --output-dir data/search_trial
```

In PowerShell use double quotes around the query. `--issue-search` accepts a GitHub issue query suffix and searches open and closed **issues**, including comment text when requested. Its results are selective and subject to GitHub's 1,000-match cap. For more coverage, run separate output directories with `--issue-search '"user-attachments" in:body,comments'`, `--issue-search 'webm in:body,comments'`, other hosts, or omit `--issue-search` for exhaustive traversal. These query runs must not be reported as a full scan. Full traversal is the only mode here that is not limited by Search's 1,000-match cap.

## Resume, caching and coverage

Run exactly the same command again to resume. Progress is committed after every discovery page and **fully processed issue**. Issue results use a transactional SQLite store (included in Python) so each checkpoint does not rewrite the entire issue corpus; repository/configuration metadata is written atomically to JSON. If a comment request fails midway, the issue is retried and previously cached comment pages are reused. Previously completed issues are skipped, and duplicate references to a video in an issue and its comments produce one pair with all source occurrences recorded. Increasing issue/repository limits in the same output directory extends the existing scan.

- `--request-budget 50` bounds uncached API attempts for this invocation; cached pages do not count.
- `--max-wait 10` pauses instead of waiting longer than ten seconds for a rate-limit reset. Defaults to 60 seconds.
- `--cache-dir data/shared_cache` shares public API/media responses between runs. Default: `OUTPUT/.cache`.
- `--no-media-probe` skips attachment HEAD requests and retains unknown attachments as `possible_video`.
- `--refresh-cache` fetches new API pages; it does not reprocess already checkpointed issues.

Exit codes: **0** requested scope finished (possibly bounded), **2** paused/interrupted with resumable outputs, **1** another collection error. Individual inaccessible repositories are recorded with `scan_status=error`, and collection continues. `finished_scope` does not mean every historical issue was scanned: check requested limits, per-repo `limited`/`exhausted`/`error` status, incomplete-search flags and `stop_reason`.

Keep `checkpoint.json` and `issues.sqlite3` together when moving a run. Caches and checkpoints are snapshots. To revisit completed issues for new comments or revised heuristics, use a **new output directory** with `--refresh-cache`; preserve the old review CSV. Changing the issue query or media-probe setting requires a new output directory. Do not run two collectors concurrently against the same output/cache directory.

## Media evidence and review scoring

Recognized media include `.mp4`, `.webm`, `.mov`, `.mkv`, `.m4v`, `.avi`, `.ogv`, YouTube, Streamable, Vimeo, Markdown links, HTML `video`/`source`, modern GitHub attachments and legacy GitHub asset/user-images URLs. Normal linked screenshots are also audited.

Opaque GitHub URLs are not assumed to be videos. The collector uses Markdown filenames, video elements, and unauthenticated HTTP **HEAD** metadata (`Content-Type`/`Content-Disposition`). Redirected probes remain HEAD requests, carry no GitHub authorization, and reject private/reserved addresses. A video element without type evidence and an opaque attachment with unavailable metadata remain `possible_video`. Explicit images/documents are excluded from the video pool but retained in rejection/audit outputs. No media bytes are downloaded. Filename/MIME/hosting evidence still cannot prove that a recording contains gameplay or reproduces the issue; misleading servers, deleted/private links and inaccessible HEAD requests remain limitations.

Scores prioritize review:

| Signal | Points |
|---|---:|
| Explicit bug/defect/crash/glitch/regression label | +2 |
| GitHub attachment with video evidence | +2 |
| “steps to reproduce” in title/body | +1 |
| Visual/gameplay keywords in title/body/labels | +1 |
| One to three distinct possible video URLs | +1 |
| Explicit logs/terminal-only wording | −2 |
| Feature request signal in title/labels | −2 |

Unlabelled issues can have bug evidence from text. Low/negative scores and missing bug evidence **do not remove possible videos**. “Likely visual bug + video” in statistics requires video evidence, bug evidence, visual keywords and score ≥5; this is still a heuristic. Generic templates can affect scores; non-English descriptions, indirect links, unusual hosts and text-only bug descriptions can be missed. Multiple videos can yield multiple pairs for one issue, so statistics report both pairs and distinct candidate issues.

## Outputs and manual validation

All outputs are under `--output-dir` and the default `data/` tree is Git-ignored:

| File | Contents |
|---|---|
| `repositories.csv` | Every discovered repo, discovery sources, metadata/license status, filter reason and scan coverage |
| `scanned_repositories.csv` | Repositories attempted, including errors and partial scans |
| `video_issue_candidates.csv` | One row per distinct issue/video URL; primary manual review file |
| `rejected_candidates.csv` | Explicit non-video links and issues with no detected media, with reasons |
| `issue_audit.csv` | Every fully scanned issue, text/dates/labels, decision, reasons and all media/source evidence |
| `collection_stats.json` | Coverage, possible/confirmed-media counts, heuristic counts, top repositories and API diagnostics |
| `checkpoint.json`, `issues.sqlite3`, `.cache/` | Resume metadata, transactional issue results, and public responses |
| `candidates.csv`, `candidates.json`, `summary.json` | Compatibility exports of candidates/statistics |

Candidate columns include repository, issue number/URL/title/body/labels, `issue_created_at`, `issue_closed_at`, video URL/type, media status/evidence, source URL/type/body/date, all source occurrences, score/reasons, `manual_valid`, and `review_notes`. Empty dates mean unavailable. `video_type` identifies the host/source and `source_type` identifies issue body versus comment.

The **legacy CSV-only workflow** allows `manual_valid` (`yes`, `no`, `uncertain`) and `review_notes` in `video_issue_candidates.csv`. The collector preserves only these two review columns on re-export/resume and copies them to JSON; edits to compatibility files are not imported. Additional CSV review columns are not preserved. The persistent Excel workflow above is the authority for the expanded review; do not maintain competing decisions in CSV and Excel. Filtered repository metadata and every scanned issue remain available for reconsideration.

Only mark **yes** when you have verified all four:

1. The repository is actual open-source game/software in the study scope (verify licensing and distinguish playable gameplay from editor/tool demos).
2. The issue describes a real bug.
3. The link contains a gameplay/video recording.
4. The recording appears to demonstrate the bug described by the issue.

No automatic output is called a validated dataset. `automatically_validated_pairs` is always zero. Follow-up work should freeze the reviewed sample, record exclusions, and measure inter-reviewer agreement before any CLIP experiment.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
```

Tests cover formats/hosts, image-vs-video evidence, metadata failure, score penalties, unlabelled and comment-only bugs, PR exclusion, pagination, API caching/budgets/rate limits, interrupted issue processing, resume and review preservation. Live results and the reproducible test command are recorded in `docs/collection-test.md`.

API contracts: [repository/issue search](https://docs.github.com/en/rest/search/search), [repository issues](https://docs.github.com/en/rest/issues/issues#list-repository-issues), [issue comments](https://docs.github.com/en/rest/issues/comments#list-issue-comments), [pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api).
