# Retrieval pilot protocol

Draft prepared on 24 November 2026. This protocol specifies a future experiment. Current accepted pairs have AI-assisted ratings and retain reviewer attribution. Human validation remains outstanding.

## Evaluation units and pool

A query is a distinct bug issue. Multiple accepted videos attached to that issue form its relevant set. Count each issue once when averaging metrics. Deduplicate identical downloaded video files by SHA-256 and retain all source URLs. When one video is relevant to multiple issues, retain all those relevance assignments.

Use the complete accepted video pool for the primary evaluation. Report a secondary within-game evaluation to expose the effect of game appearance. Record the number of queries, unique video files, repositories and relevant files per query. Recall@5 on a small pool should be interpreted with its pool size.

## Text conditions for RQ2

Compare title only, title plus cleaned body, and title plus structured reproduction/expected/actual sections. Derive these from source issue text. Preserve the described symptoms and record missing sections. Exclude attachment addresses, template boilerplate and filenames used only as media references. Use identical video pools and query sets for all conditions. Freeze the text processing before the final evaluation.

CLIP input length and truncation must be recorded with the eventual selected model. Record which queries are truncated. Choose and freeze any chunking policy on development examples before measuring final results.

## Frame and video representation

For the first baseline sample one frame per second, including time zero, and use the same frame policy for every recording. Retain timestamps, duration, decoder version and failed-decode status. Use the selected pretrained model's prescribed image preprocessing. L2-normalize frame and query embeddings. Score a video using the maximum cosine similarity over its frames. Report that maximum scoring can favor longer recordings and examine that limitation when interpreting results.

## RQ1 metrics

Rank distinct video files by descending score, with a stable file-ID tie break. For each issue, Recall@k is the fraction of its relevant files present among the first k results. Report macro-average Recall@1 and Recall@5. Also report Hit@1 and Hit@5, which measure whether at least one relevant video is retrieved, and MRR using the first relevant rank. These definitions matter for issues with multiple recordings.

## RQ3 categories and analysis

Use the recorded primary symptom category. Report query counts per category and per game alongside scores. Treat categories with very few issues as descriptive examples. Build connected components of the issue-to-video-SHA-256 graph and keep each component together in any development/evaluation partition. This groups recordings of the same issue and shared recordings linked from different issues. Freeze model, preprocessing and scoring choices using development examples before the final evaluation. If the sample remains too small to reserve a separate evaluation set, label the entire run exploratory.

## Reproducibility

Save model name and checkpoint, package versions, source snapshot, query variants, candidate IDs, video hashes, sampled timestamps, full rankings and per-query metrics. Preserve rejected and uncertain records with reasons. Future additions require a new dataset snapshot and rerun.

## Follow-up exploratory conditions

The text-chunk condition uses the same videos, model, image embeddings and queries as the truncation baseline. Split each complete text's content token sequence into consecutive non-overlapping windows of at most 75 tokens, adding start/end tokens to each window. Normalize chunk embeddings and score a video with the maximum similarity across all its frames and all query chunks. This retains long text, but maximum scoring may favor queries with more chunks as well as longer videos. Preserve the truncation run and save chunk results separately. These choices were made after inspecting pilot aggregate results, so this follow-up is exploratory.

Report an analytical random-ranking reference for each actual pool size and number of relevant videos. Expected Recall@k is min(k,N)/N. Expected Hit@k uses the probability that a uniformly random top-k subset contains at least one relevant video. Expected reciprocal rank sums the probability that the first relevant video occurs at each rank, weighted by the reciprocal rank. Average per issue with the same relevance groups used for model evaluation.

Select six baseline failures for frame/source inspection as diagnostic examples. Record timestamps, source issue, failed text conditions and limitations. This selection describes individual cases and cannot estimate overall annotation accuracy.
