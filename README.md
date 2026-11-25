# From Bug Reports to Gameplay Videos

Variant B research project exploring whether CLIP can retrieve gameplay videos from bug reports in open-source game repositories.

The Python collector discovers repositories, scans issues and comments, and saves candidate report/video pairs for review. Separate scripts run retrieval experiments on the reviewed dataset.

## Collect candidates

The collector requires Python 3.10+ and uses the standard library. Run these commands from the project folder, including in the VS Code terminal.

```bash
python3 scripts/collect_candidates.py --discover-only --max-repos 100 --output-dir data/discovery
python3 scripts/collect_candidates.py --repos repos.example.txt --max-issues-per-repo 3 --output-dir data/trial
```

To discover repositories and scan a larger sample in one run:

```bash
python3 scripts/collect_candidates.py --max-repos 100 --max-scan-repos 10 --max-issues-per-repo 100 --output-dir data/pilot
```

On Windows, use `python` or `py -3`. Set `GITHUB_TOKEN` in the terminal environment for higher GitHub API limits. The script reads environment variables directly. Keep tokens out of committed files.

Issues and comments are paginated. Video detection covers GitHub attachments, direct video files, YouTube, Vimeo and Streamable. HTTP metadata helps distinguish videos from images. Scores prioritize candidates for review.

Repeat the same command to resume a paused run. Keep `checkpoint.json` and `issues.sqlite3` together. Use a new output directory when changing the search query or revisiting completed issues. Exit code 2 means collection paused with resumable outputs. Run `python3 scripts/collect_candidates.py --help` for search, caching and request-budget options.

## Review the pairs

A pair qualifies when the repository fits the study scope, the issue describes a bug, and the video shows gameplay demonstrating that bug. Record uncertain cases and reasons for exclusions.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-review.txt
.venv/bin/python scripts/review_workbook.py sync --run-dir data/pilot --workbook data/review/review.xlsx
.venv/bin/python scripts/review_workbook.py export --workbook data/review/review.xlsx --output-dir data/validated
```

Close the workbook before syncing. Existing reviews are preserved. Keep review decisions in the workbook. The [review guide](docs/manual-review.md) explains the fields and recovery steps.

## Outputs

Each collection run saves these files under `--output-dir`.

| File | Contents |
| --- | --- |
| `repositories.csv` | Discovered repositories, metadata and filtering decisions |
| `scanned_repositories.csv` | Scan coverage and errors |
| `video_issue_candidates.csv` | Candidate issue/video pairs with text, links, labels, dates and scores |
| `rejected_candidates.csv` | Rejected records and reasons |
| `issue_audit.csv` | Scanned issues and media evidence |
| `collection_stats.json` | Counts, coverage and API diagnostics |

The `data/` directory is ignored by Git. Back up review work, downloaded videos and experiment outputs separately.

## Retrieval pilot

The local pilot contains 30 accepted pairs from 25 issues across six repositories. Ratings were made by AI assistants, with independent AI checks. Human validation remains outstanding.

OpenAI CLIP ViT-B/32 was evaluated on 30 videos and 1191 sampled frames. On the complete pool, Recall@5 was 54% for titles and 68% for both longer text variants. Splitting long text into chunks gave 66% and 62%. Expected random Recall@5 was 16.7%.

These are exploratory results from a small, uneven sample. Some queries were truncated, and several videos belong to the same issue. The conservative sensitivity subset contains 23 issues and 27 videos.

Experiment scripts require Python 3.11+, optional dependencies in `requirements-clip.txt`, FFmpeg and the reviewed local data. Follow the [run guide](docs/run-clip-pilot.md) for installation and commands.

- [Dataset and scope](docs/dataset-progress.md)
- [Experiment protocol](docs/experiment-protocol.md)
- [Text comparison and error analysis](docs/clip-followup.md)
- [Sensitivity analysis and confidence intervals](docs/clip-robustness.md)
- [Working article](paper/README.md)

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
```

The suite covers collection, media detection, resume behavior, review preservation, retrieval metrics, text preparation and statistical analysis. NumPy-dependent checks require the optional experiment dependencies.
