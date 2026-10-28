# Working article

English working draft for Variant B, keeping the three research questions provided by Ivan on 28 October 2026. Collection observations are measured; the CLIP evaluation is explicitly planned. Read and revise the draft before submission. No model results or manual validations have been invented.

## Template provenance

The class and bibliography style are copied unchanged from the TUKE FEI EEI 2026 article template:

- https://eei.fei.tuke.sk/for-authors/
- https://eei.fei.tuke.sk/wp-content/uploads/2026/05/LaTeX_template.zip
- Downloaded 2026-10-28. The old 2024 archive linked by the KPI page returned 404.

The template uses IEEEtran with `journal,a4paper,onecolumn`. The publisher's 5–8-page rule concerns EEI submissions; the supplied ESS course text does not prescribe that limit or require submission to EEI. The draft uses the layout for this course article. Original class/style copyright and license notices remain in those files. No submission to an external conference or journal is performed.

## Compile in WSL / VS Code

```bash
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

Open `paper/main.tex` with LaTeX Workshop if installed. The PDF is `paper/build/main.pdf`; `.latexmkrc` directs builds there. `latexmk -c -outdir=build main.tex` removes temporary build files. The source and bibliography belong in Git; generated files are ignored.

## Before the final article

- Confirm scope, codebook, text variants, candidate pools and evaluation protocol with the instructor.
- Complete and freeze manual review; replace candidate counts with a clearly distinguished reviewed dataset summary.
- Implement and execute CLIP preprocessing and retrieval. Record actual versions, settings, failures and outcomes.
- Replace planned evaluation language with the executed procedure and answer RQ1–RQ3 using measured results.
- Expand related work. Check `docs/literature-notes.md` for current evidence and lookup limits.
- Describe AI assistance according to the course/instructor's requirements. This draft and tooling were prepared with Codex assistance; scientific interpretation and final authorship require Ivan's review.
