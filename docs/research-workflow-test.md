# Paper and review workflow verification — 2026-10-28

Branch: `research/paper-and-review`. Baseline: commit `1792a32`, 31 existing tests passed. The original collector and pilot outputs were not regenerated.

## Executed checks

- WSL Ubuntu, Python 3.12.3, isolated `.venv`, openpyxl 3.1.5.
- `.venv/bin/python -m unittest discover -s tests -q`: **43 tests passed** (31 existing, 12 new optional review tests).
- `.venv/bin/python -m compileall -q scripts tests`: passed.
- Whitespace checks passed for authored files. The unchanged vendor `IEEEtran.cls` and `IEEEtran.bst` retain their original trailing whitespace and are excluded from the staged whitespace gate; their source contents were preserved intentionally.
- Real sync from `data/pilot`: **67 pairs**, **6 repositories**. All new review prerequisites remain blank; no recording was watched or marked valid automatically.
- Immediate repeated sync: **0 pairs added, 0 repositories added, saved=false**. Tests independently verify byte and modification-time preservation on no-op.
- Initial validated export: **0 pairs**.
- Tests cover retained old candidates and reviews, custom columns/sheets, basic formulas, styles and ordinary text comments, input duplicates and exact URL variants, sorted rows/reordered columns, open/sync locks, injected save/backup/replace errors, every inclusion prerequisite, literal XLSX text and escaped CSV/original JSON text.
- Workbook imported and inspected with Artifact Tool: `Pairs!A1:W68`, `Repositories!A1:J7`. Both sheets and the source/link region were rendered and visually reviewed. Frozen panes C2/B2, six/two validation ranges, filters and conditional decision formatting were checked through saved-file inspection. Actual manual editing in desktop Excel/LibreOffice was not automated.
- TUKE EEI 2026 template downloaded successfully from the current official For Authors page. Class and bibliography style copied unchanged. The previously linked 2024 archive returned 404.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex`: succeeded, four A4 pages. Bibliography resolved. All four pages visually reviewed; exact RQ1–RQ3 retained. The vendor template emits small 4.6pt output-box warnings; no content clipping was observed. The paper clearly distinguishes the collection pilot from future manual validation/CLIP results.

## OMX review

OMX was invoked through its installed WSL CLI in read-only mode for an initial design review and an independent implementation review. Plan feedback led to an explicit XLSX review authority, strict export prerequisites, backup verification, supported-workbook bounds and realistic concurrency limits.

The implementation review identified CSV formula injection in the new validated export. This was corrected by escaping formula-leading CSV text while preserving original JSON strings, with regression coverage. A separate targeted OMX recheck independently reproduced dangerous-prefix and CSV/JSON cases and confirmed that this specific blocker was fixed. The broader review reported its architecture lane unavailable because that lane's configured model was unsupported; no claim of that lane's approval is made. Review notes remain under the local `.omx/plans/` directory rather than being part of the public dataset.

## Remaining work

Manually review repository eligibility and every candidate, refine/freeze codebook and study choices with the instructor, then implement and execute the CLIP experiment. Neither passing software tests nor MIME/video evidence constitutes a validated research pair. Keep the workbook closed during sync and back up the ignored data directory separately.
