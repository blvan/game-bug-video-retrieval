# Initial literature evidence — 2026-10-28

This is an initial related-work set, not a systematic review. Metadata and available excerpts were checked through the connected Scite `search_literature` tool. Scite returns only the first three authors; BibTeX therefore uses `and others`, not an invented complete author list. The original CLIP proceedings page supplies venue/volume/pages. Returned records did not include an `editorialNotices` field; this does not certify the absence of later corrections or retractions. Recheck before final submission.

| Paper | Identifier | Supported use in the draft |
|---|---|---|
| Radford, Kim, Hallacy, et al. (2021), Learning Transferable Visual Models From Natural Language Supervision | arXiv:2103.00020; https://proceedings.mlr.press/v139/radford21a.html | Paired image/text supervision and transferable image representations. No claim of gameplay bug understanding. |
| Cooper, Bernal-Cárdenas, Chaparro, et al. (2021), It Takes Two to Tango | https://doi.org/10.1109/ICSE43902.2021.00091 | Related work on duplicate video-based bug reports combining visual and textual information. |
| Yan, Cooper, Chaparro, et al. (2024), Semantic GUI Scene Learning and Video Alignment for Detecting Duplicate Video-based Bug Reports | https://doi.org/10.1145/3597503.3639163 | Related work on GUI scene representation and video alignment for duplicate reports. |

Evidence excerpts returned by Scite (short quotations):

- Janus, paper excerpt: “Janus receives as input two video-based bug reports and outputs a similarity score”. This supports the distinction between video-to-video duplicate detection and our text-to-video query.
- Tango, full-text citation statement: “determining whether two videos depict and report the same bug”. The statement is context for that paper's task; its mentioning classification is not independent evidence that our approach works.
- CLIP's Scite lookup returned metadata but no full-text excerpt. The original PMLR abstract states “predicting which caption goes with which image”; use the original paper for the method description.

Do not copy another paper's benchmark numbers into this study's results. No inference that these methods have been evaluated on our game dataset is supported. No external collection, message, or publication was created in Scite.

## References

Radford, A., Kim, J. W., Hallacy, C., et al. (2021). Learning transferable visual models from natural language supervision. *Proceedings of Machine Learning Research, 139*, 8748–8763. https://proceedings.mlr.press/v139/radford21a.html

Cooper, N., Bernal-Cárdenas, C., Chaparro, O., et al. (2021). It takes two to Tango: Combining visual and textual information for detecting duplicate video-based bug reports. *ICSE*, 957–969. https://doi.org/10.1109/ICSE43902.2021.00091

Yan, Y., Cooper, N., Chaparro, O., et al. (2024). Semantic GUI scene learning and video alignment for detecting duplicate video-based bug reports. *ICSE*, 1–13. https://doi.org/10.1145/3597503.3639163
