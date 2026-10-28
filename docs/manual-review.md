# Persistent manual review

The Excel ledger is the authority for the expanded review. Raw collector runs remain snapshots; the optional review command does not modify them or the API cache. The existing collector still preserves only `manual_valid`/`review_notes` in its primary CSV. Editing that CSV later does not overwrite decisions already imported into the ledger. Do not maintain competing reviews in both places.

## Install and run in WSL

```bash
cd /home/ivand/5rocnik/ESS/game-bug-video-retrieval
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-review.txt
.venv/bin/python scripts/review_workbook.py sync --run-dir data/pilot --workbook data/review/review.xlsx
```

The initial ledger contains 67 pairs and six repositories from `data/pilot`. These are candidate counts. No recording was automatically marked reviewed. Open `data/review/review.xlsx` in Excel or LibreOffice.

After a later collection run, close the workbook and append that run:

```bash
.venv/bin/python scripts/review_workbook.py sync --run-dir data/new_run --workbook data/review/review.xlsx
```

Repeat `--run-dir` to combine several runs in one sync. Existing pairs are identified by lower-case repository, positive issue number, and exact trimmed video URL (query strings/fragments retained). Different issues using the same URL remain separate pairs. The first imported snapshot wins; reruns do not refresh old metadata or manual cells. Identical candidate keys across runs add only one row. Do not change identity columns or IDs. Sorting entire rows, reordering named columns, adding your own columns and adding plain notes sheets are supported. Do not sort one column independently.

## Review fields

Blank means unreviewed; `yes`, `no`, `uncertain` are explicit decisions. Automatic scores are priorities for viewing, not ground truth. Start with a diverse subset across repositories and scores, then review all pilot pairs.

**Repositories:** `scope_valid` means the repository is a playable open-source game within the study scope; `license_verified` means you inspected its software license. Record the license/source and scope reasoning in `review_notes`, then fill `reviewer` and `reviewed_at`. Software licensing does not grant recording redistribution rights.

**Pairs:**

- `video_accessible`: the linked recording can actually be viewed.
- `is_gameplay`: it contains gameplay. Editor/tool demonstrations and interface-only sites are outside the initial scope. A HUD fault visible during gameplay can qualify.
- `describes_bug`: the report describes a fault, not merely a feature request.
- `matches_report`: the observable recording symptom corresponds to the report. This does not establish a root cause.
- `bug_category`: primary visual symptom using the provisional codebook below.
- `manual_valid`: final inclusion decision. Set yes only after checking the prerequisites. No/uncertain remain in the ledger.
- `review_notes`: evidence, video timestamps if useful, exclusions and uncertainty; `reviewer` and `reviewed_at`: who checked and when.

If an imported legacy CSV has `manual_valid=yes`, the other checks are still blank and must be completed. Color is a visual cue only; export uses cell values. The workbook has filters, frozen identifiers/headers, dropdowns and clickable issue/video source URLs. Long source bodies above Excel's 32,767-character cell limit are explicitly truncated in Excel; full text remains in the original run.

## Provisional codebook v0.1

Assign one primary category before viewing CLIP results:

| Value | Definition |
|---|---|
| `rendering` | Missing/wrong sprites, textures, lighting, effects or visible HUD rendering during gameplay |
| `animation` | Incorrect pose, animation transition, timing or movement animation |
| `camera` | Wrong viewpoint, following, zoom, clipping or camera motion |
| `spatial_collision` | Visibly demonstrated collision/position/geometry faults, such as falling through a track |
| `other_visual` | Other visible gameplay faults; explain why in notes |

Select the dominant reported symptom; record secondary symptoms in notes. Review a small diverse subset to refine this codebook, then update the version and freeze it before measuring RQ3. Do not invent categories after inspecting which ones perform well. If available, ask a second reviewer to independently label a subset and record disagreement resolution. Otherwise report the single-reviewer limitation.

## Export reviewed data

```bash
.venv/bin/python scripts/review_workbook.py export --workbook data/review/review.xlsx --output-dir data/validated
```

This produces `validated_pairs.csv` and `validated_pairs.json`. Every included pair must have final yes, all four pair checks yes, both repository checks yes, and a recognized category. An inconsistent yes decision aborts the export before files are replaced, listing missing prerequisites. With the initial unreviewed ledger the export contains zero rows. A successful export is a reviewed input manifest, not an executed CLIP experiment. CSV text that could be interpreted as a spreadsheet formula is prefixed with an apostrophe. JSON preserves the original strings and is the preferred input for RQ2 text processing; do not treat CSV escape characters as part of the report.

## Preservation and recovery

- Existing rows, manual values, order, and custom columns are not changed during sync; missing old candidates are not deleted. A no-op leaves workbook bytes/mtime unchanged and makes no backup.
- Changed syncs create byte-verified timestamped backups in `data/review/backups/` and validate a temporary XLSX before same-directory atomic replacement. Save/backup/replace failure leaves the old workbook in place.
- Synchronization uses an exclusive `.sync.lock`, common Excel/LibreOffice open-file markers, and a content hash check before replacement. Always close the workbook first. These checks cannot universally detect an application that ignores locks or saves in the tiny interval after the final check. Do not sync on two machines simultaneously.
- A lock left by a crashed process must be removed only after confirming no sync is active. To recover a backup, close the workbook, retain a copy of the current file, and copy the selected backup to the ledger path.
- Supported: this plain `.xlsx` template, basic cells/styles/formulas, data validation, ordinary text comments and additional plain sheets. Charts, embedded media, pivots, macros, external links, threaded comments and rich data are rejected. Do not add complex Excel features; their arbitrary preservation is not promised. Formulas in manual decision fields cannot qualify as yes. Text from issues is written as literal text.
- The whole `data/` tree, including reviews and backups, is Git-ignored. Back it up separately; a Git commit of code does not back up manual work. Versioned dataset releases can be exported intentionally after review, with their provenance and sharing rights checked.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Regression tests cover append/no-op, duplicates and exact URL variants, retained reviews and missing old rows, reordered columns/rows, extra sheets, literal text, locks, save/backup/replace failures, prerequisites and validated export. Native Excel/LibreOffice editing is a user step; generated-file inspection alone does not test every application feature.
