# Pilot sensitivity and uncertainty

Independent dense-frame review retained uncertainty for CDDA #65241 and AzerothCore #28192. The first lacks visible input evidence to establish the reported navigation trigger. The second begins during an encounter and does not independently establish the expected combat phase or test state. Observed symptoms remain documented. Both issues are excluded from a conservative sensitivity analysis. The primary ledger remains unchanged. This post-hoc analysis does not create human-validated ground truth.

Full evaluation contains 25 issues and 30 videos. Query-only sensitivity keeps 30 videos and evaluates the remaining 23 issues. Query-and-video sensitivity evaluates 23 issues against 27 videos, removing only recordings exclusively associated with excluded issues. The two settings distinguish query selection from changing distractors.

For global structured-text truncation, Recall@5 is 0.68 with a 95% percentile bootstrap interval [0.48, 0.84]. Excluding flagged queries gives 0.739 with interval [0.565, 0.913]. Query-and-video restriction has the same Recall@5 here. These broad intervals indicate uncertainty on this small pilot.

Use paired issue resampling to compare conditions. There are 10,000 resamples with seed 20261124. On the full global pool the structured-minus-title Recall@5 difference is +0.14 [0.02, 0.28]. Chunked-minus-truncated structured text gives -0.06 [-0.16, 0]. The sample, preprocessing follow-up and exclusions were selected during exploratory analysis. These intervals support descriptive pilot interpretation and do not establish confirmatory superiority. Resampling assumes independent issues and does not capture uncertainty in AI relevance labels, repository-level dependence or dataset discovery bias.

```bash
.venv/bin/python scripts/evaluate_robustness.py
```

Results and input hashes are in `data/experiments/clip-robustness/`. The dense-frame adjudication is in `data/review/adjudication-current.json`. All generated data is local and ignored by Git. Preserve these directories when sharing or archiving the experiment. The committed scripts and documented aggregate results alone cannot reconstruct remote attachments that later disappear.

Future retrieval runs record source hashes. The original completed manifests predate that addition and contain model, input and package provenance. Their historical records are retained as produced.
