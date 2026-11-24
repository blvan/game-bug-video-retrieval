# Dataset preparation progress

Snapshot date is 24 November 2026. The local reviewed pool contains 30 accepted video pairs for 25 distinct issues across six repositories. All ratings are AI-assisted decoded-frame assessments with timestamps and reviewer attribution. Human validation is outstanding. These counts describe a research pilot.

| Repository | Accepted video pairs |
| --- | ---: |
| OpenRCT2/OpenRCT2 | 12 |
| wesnoth/wesnoth | 7 |
| CleverRaven/Cataclysm-DDA | 5 |
| azerothcore/azerothcore-wotlk | 3 |
| ppy/osu | 2 |
| SuperTux/supertux | 1 |

All 30 accepted files are persisted under `data/media/` with SHA-256 hashes in `data/validated/media_manifest.json`. Exact duplicates are checked by file hash. Shared issues are retained as relevance groups. Hash deduplication cannot detect re-encodings or semantically equivalent recordings.

`data/validated/validated_pairs.csv` and `.json` contain reviewed pairs. `data/validated/dataset_snapshot.json` fixes artifact hashes and counts. The authoritative workbook remains `data/review/review.xlsx`. Detailed assessment packets and rating revisions are retained in `data/review/expansion-evidence/`. Local data is ignored by Git.

Three previously inaccessible recordings were recovered using curl and reassessed. Two were accepted, one remained uncertain. Earlier decisions are preserved in revision evidence and workbook backups. The historical URL audit found four broken Markdown representations, two with recoverable destinations that returned 404 and two with unsupported placeholder destinations.

The scope includes open-source game implementations with external proprietary dependencies. OpenRCT2 requires original game assets, and AzerothCore recordings require a proprietary World of Warcraft client/assets. AzerothCore and some SuperTux/CDDA reproductions use test or debug environments. These conditions must be retained in interpretation and any later subset selection. Source-code licensing does not establish permission to redistribute recordings.

Category counts are 14 other_visual, 9 rendering, 4 spatial_collision, 2 animation and 1 camera. This distribution supports exploratory examples; category comparisons are especially limited for animation and camera. Multiple clips of one issue do not create additional independent queries.

`docs/experiment-protocol.md` specifies frame sampling, text conditions, scoring, Recall, Hit and MRR. `data/review/rq2-current.json` provides draft text variants for all 25 issues and records missing structured sections. Text cleanup and truncation policy still need checking against the selected model before the final evaluation. Full rankings and model results will follow in a later execution stage.

All 46 existing tests pass after the Markdown parser fix. The current independent artifact check is recorded separately in `data/review/verification-final.json`. Article work is a separate stage.
