# Collection test — 2026-10-21

Environment: Python 3.12.3, standard library only, no `GITHUB_TOKEN` set. No CLIP code or video downloading.

## Original coverage

The earlier smoke test covered only the three manually listed repositories and three newest issues each: nine issues, nineteen comments, and three attachment links across two repositories. It did not establish the number of usable repositories/pairs on GitHub. The original collector already paginated issues and comments but had no repository discovery or resume support, recognized fewer media sources, and assumed all opaque GitHub attachments were video.

## Reproducible pilot

From the repository root:

```bash
python3 scripts/collect_candidates.py --topics opensource-game,roguelike,strategy-game,game,racing-game --per-topic 40 --max-repos 100 --max-scan-repos 6 --max-issues-per-repo 10 --issue-search 'mp4 in:body,comments' --output-dir data/pilot --cache-dir data/discovery_trial/.cache --request-budget 10 --max-wait 10
```

The API responses were first fetched live into the shared cache. An initial ten-repository attempt paused at its 50-request budget after 55 issues; resuming completed a bounded six-repository pilot without losing the completed issues. The final implementation replayed the public cached API responses (59 cache hits, zero additional API requests) and performed/reused HEAD media checks. The command above may need several resumes on an empty cache because of its deliberately small request budget. Results can change when fetched afresh.

The discovery target is a minimum desired pool, not an exact count; whole result pages and filtered matches are retained. All six scanned repositories reached their **ten matching issues** limit, not the end of their history. The query is selective; these results are not an exhaustive or random sample.

## Results

| Measure | Count |
|---|---:|
| Repositories discovered | 124 |
| Repositories retained for scanning (metadata candidates) | 117 |
| Repositories scanned | 6 |
| Issues fully scanned | 60 |
| Comments scanned | 273 |
| Issues containing detected media | 53 |
| Issues with possible videos | 47 |
| Possible issue/video pairs | 67 |
| Pairs with filename/host/MIME video evidence | 51 |
| Pairs with uncertain media type | 16 |
| Heuristically likely visual bug/video pairs | 15 |
| Repositories with at least one candidate | 6 |
| Explicit non-video media links excluded | 78 |
| Automatically validated pairs | 0 |

Top repositories (all counts remain candidates):

| Repository | Pairs | Distinct issues |
|---|---:|---:|
| wesnoth/wesnoth | 17 | 10 |
| azerothcore/azerothcore-wotlk | 15 | 10 |
| OpenRCT2/OpenRCT2 | 12 | 8 |
| CleverRaven/Cataclysm-DDA | 9 | 7 |
| ppy/osu | 8 | 7 |
| lichess-org/lila | 6 | 5 |

## Ten representative issue URLs

Selected for repository diversity, visual/gameplay signals and comment-only recordings; this is not a random sample or a validated selection. Scores can underrank useful bugs (for example the coaster report) and overrank non-gameplay UI reports. The video URL and source text for every example are in the primary review CSV.

| Candidate issue | Score | Video occurrence |
|---|---:|---|
| [wesnoth/wesnoth#6960: Unit's image is missing when attacking](https://github.com/wesnoth/wesnoth/issues/6960) | 7 | comment |
| [wesnoth/wesnoth#7163: Interaction between the square highlight and the icon overlay of a unit and other overlay glitches](https://github.com/wesnoth/wesnoth/issues/7163) | 6 | issue |
| [wesnoth/wesnoth#11106: Halos bleed through sidebar under certain conditions](https://github.com/wesnoth/wesnoth/issues/11106) | 5 | issue |
| [OpenRCT2/OpenRCT2#22116: Coaster falling through track](https://github.com/OpenRCT2/OpenRCT2/issues/22116) | 4 | issue |
| [OpenRCT2/OpenRCT2#19506: Queue paths are able to be placed on train tracks.](https://github.com/OpenRCT2/OpenRCT2/issues/19506) | 6 | issue |
| [CleverRaven/Cataclysm-DDA#84543: Odd graphical glitches in the unsprited part of the overmap tileset](https://github.com/CleverRaven/Cataclysm-DDA/issues/84543) | 3 | issue |
| [CleverRaven/Cataclysm-DDA#64340: Uzi 9x19mm issue with integrated folding stock](https://github.com/CleverRaven/Cataclysm-DDA/issues/64340) | 5 | comment |
| [ppy/osu#38938: Map freezes (softlocks) seemingly at random](https://github.com/ppy/osu/issues/38938) | 1 | comment |
| [azerothcore/azerothcore-wotlk#28183: [DEATHKNIGHT]Archerus teleporter - Front part teleports to the same level](https://github.com/azerothcore/azerothcore-wotlk/issues/28183) | 2 | issue |
| [lichess-org/lila#12544: Toggling computer analysis produces console error and "shake"/scroll the screen.](https://github.com/lichess-org/lila/issues/12544) | 7 | comment |

## Artifacts and validation

Local outputs: `data/pilot/repositories.csv`, `scanned_repositories.csv`, `video_issue_candidates.csv`, `rejected_candidates.csv`, `issue_audit.csv`, `candidates.json`, `collection_stats.json`, and the compatibility exports. The Git-ignored `data/` tree also holds `checkpoint.json`, `issues.sqlite3` and response caches. Raw issue bodies and findings were not committed; this report preserves the run summary and public example URLs.

- Unit/regression tests: 27 passed (`python3 -m unittest discover -s tests -v`).
- `python3 -m compileall -q scripts tests` and `git diff --check` passed.
- CSV/JSON pair counts, repository/issue audit counts and SQLite integrity were checked.
- A subsequent completed-pilot resume used zero API requests, retained all 60 issues and 67 unique pairs, and left all manual validity cells blank.
- The live API-budget pause/resume retained previous issues; regression tests also verify mid-comment failure recovery and preservation of manual review cells.

## Limits and research interpretation

- No recording was watched as part of automatic collection. Video evidence does not prove gameplay, a real bug, or correspondence with the issue. `manual_valid` remains blank for all 67 pairs.
- Modern opaque attachments without filenames are not covered by the `mp4` search unless another part of the issue/comments matches; run additional host/extension searches or full pagination without `--issue-search`.
- GitHub Search reported more than 1,000 matches for the broad game-topic search and osu's issue query. The pilot requested only a small bounded subset; exhaustive traversal must use the ordinary issue endpoint or partitioned searches. `incomplete_results` flags were absent in this run.
- Thirty-eight discovered repositories need licensing review. Topic/description checks also retain possible engines/tools and server implementations; verify study scope and licensing manually. Lichess interface reports and AzerothCore recordings may need exclusion or scope decisions; their presence does not establish playable, fully open-source gameplay footage.
- Audio-only reports, UI-only videos, unrelated demonstrations, boilerplate bug templates and feature requests can enter the broad pool. Review the recording and full issue, do not use score alone.
- HEAD failures, inaccurate filenames/MIME, inaccessible/deleted links, external indirections, non-English bug wording and untagged/low-star repositories limit recall or precision. Linked PR comments are not fetched.
- Cached responses are snapshots. A fresh output directory with refreshed API cache is required to revisit completed issues for later comments. The pilot does not estimate the total number of valid repositories/pairs.

Use `manual_valid=yes/no/uncertain` and `review_notes` in `video_issue_candidates.csv`. Mark yes only after verifying the repository scope/license, an actual bug, a gameplay/video recording and the recording's correspondence with the bug. No research definition was weakened to increase these candidate counts.
