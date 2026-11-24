# Run the exploratory CLIP pilot

The pilot uses the accepted local dataset and persisted media manifest. Ratings are AI-assisted and human validation remains outstanding. OpenAI ViT-B/32 weights are loaded through OpenCLIP with QuickGELU. This is a CPU baseline.

The optional experiment scripts require Python 3.11 or later. Install CPU PyTorch into the project virtual environment, then the optional retrieval dependencies.

```bash
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-clip.txt
.venv/bin/python scripts/prepare_queries.py --help
.venv/bin/python scripts/prepare_queries.py
.venv/bin/python scripts/run_retrieval.py --ffmpeg /path/to/ffmpeg
```

The actual session used `/tmp/ess-w5-media/tools/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v9.0.2`. Supply an installed FFmpeg executable on other machines. The first run downloads pretrained weights to `data/clip-cache`. Frame embeddings are cached separately and can be reused on reruns.

Results are saved under `data/experiments/clip-pilot/`. `rankings.csv` contains complete rankings, `per_query.csv` contains issue-level metrics, `metrics.json` includes overall and grouped aggregates, `text_inputs.json` records text and truncation, and `run_manifest.json` records configuration, input hashes, model state hash, package versions and sampled timestamps. Check its completion status before interpreting the outputs.

The three text conditions use identical queries and video pools. Text is truncated to CLIP's 77-token context and truncation is recorded. Additional-context and triage sections are omitted by the fixed exploratory cleanup policy, which can remove useful secondary information. Pool size, category imbalance, longer-video maximum scoring and AI-assisted relevance labels limit interpretation. Within-game pools can be very small, so report those sizes beside retrieval metrics.

## First completed run

On 24 November 2026 the CPU run completed for 25 issue queries, 30 unique videos and 1191 sampled frames. Each text condition used the same pools and relevance assignments.

| Text condition | Global Recall@1 | Global Recall@5 | Global MRR |
| --- | ---: | ---: | ---: |
| Title | 0.28 | 0.54 | 0.4363 |
| Title and cleaned body | 0.26 | 0.68 | 0.4500 |
| Title and structured sections | 0.28 | 0.68 | 0.4572 |

Recall averages the fraction of relevant files recovered per issue. Hit@1 differs for issues with multiple videos and is also available in the saved metrics. The largest observed global Recall@5 is shared by both longer text conditions. These descriptive pilot differences do not establish a statistically reliable improvement.

Nineteen cleaned-body queries and eighteen structured queries exceeded 77 tokens and were truncated. Title queries were within context. Any later chunking comparison must be saved as a new experimental condition. Maximum-over-frames scoring can favor longer videos. Within-repository Recall@5 is especially easy for pools of five or fewer recordings and should be read alongside pool sizes.

Dependencies used were torch 2.15.0+cpu, torchvision 0.29.2+cpu and open_clip_torch 4.2.2. Full versions and hashes are in the run manifest. Two implementation findings were corrected before the completed run: OpenAI weights require QuickGELU, and a stale extracted PNG must be removed before each new frame extraction. The completed run uses the corrected v2 cache key.
