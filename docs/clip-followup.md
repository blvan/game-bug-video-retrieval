# Exploratory text and random-baseline comparison

The follow-up uses the same 25 issues, 30 videos, model weights, 1191 frame embeddings and relevance assignments as the first pilot. Text windows contain consecutive, non-overlapping sequences of up to 75 content tokens. Scoring takes the maximum over frames and text chunks. This is a follow-up exploratory condition chosen after inspecting the truncation pilot.

| Condition | Global Recall@1 | Global Recall@5 | Global MRR |
| --- | ---: | ---: | ---: |
| Expected random ranking | 0.0333 | 0.1667 | 0.1478 |
| Title, truncation | 0.28 | 0.54 | 0.4363 |
| Cleaned body, truncation | 0.26 | 0.68 | 0.4500 |
| Structured text, truncation | 0.28 | 0.68 | 0.4572 |
| Cleaned body, chunks | 0.22 | 0.66 | 0.4298 |
| Structured text, chunks | 0.22 | 0.62 | 0.3940 |

Retaining all text with this maximum-chunk rule did not improve these aggregate pilot metrics. No statistical superiority claim follows from these small exploratory differences. Maximum scoring introduces more opportunities for a high similarity score as text chunks or video frames increase.

The random reference is the exact expectation under uniformly random rankings for each actual pool and relevant-file count. It does not require sampled seeds or repeated random shuffles. Macro averaging uses each issue once per pool. Recall and Hit differ for issues with multiple relevant videos.

Reproduce from the project root with the installed optional CLIP requirements and a local FFmpeg executable.

```bash
.venv/bin/python scripts/run_retrieval.py --text-mode chunks --output-dir data/experiments/clip-chunks --ffmpeg /path/to/ffmpeg
.venv/bin/python scripts/analyze_retrieval.py --help
.venv/bin/python scripts/analyze_retrieval.py
```

Complete chunk rankings, metrics, token IDs and run provenance are in `data/experiments/clip-chunks/`. Random expectations and diagnostic failure records are in `data/experiments/clip-analysis/`. Six selected failed issues receive independent frame/source review with timestamps. This deliberate sample diagnoses particular cases and does not estimate annotation accuracy. Ratings remain AI-assisted and human validation remains outstanding.

## Diagnostic frame review

An independent AI assessor inspected six deliberately selected structured-text failures across five games, with original reviewer notes withheld. The saved `error_review.json` includes source links, timestamps, contact sheets, relevant ranks and incorrectly retrieved top results.

The examples show that small visual changes and sequences of actions can be difficult for isolated-frame similarity. OpenRCT2 #20684 visibly loses path accessories between sampled frames, while its first relevant rank is below five. This is an observed case; the explanation that scene similarity dominates the symptom is a hypothesis.

Two cases warrant stronger relevance evidence in later validation. CDDA #65241 visibly changes inventory selection, but sparse frames cannot establish which keys were pressed. AzerothCore #28192 requires proving an expected combat phase was skipped, which a short sequence of still frames cannot establish fully. These flags are retained in the diagnostic review. Existing dataset ratings are preserved, and no human-gold claim is made.
