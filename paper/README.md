# Paper assets

This folder holds the ASE 2026 Tools & Datasets Track submission, the
screencast script, and the ACM `acmart` template support files lifted from
the Overleaf bundle (`AI_Aware_Threat_Library_ACM.zip`) so the paper builds
identically locally and on Overleaf.

## Files

- `paper.tex` — full 4-page draft. Uses
  `\documentclass[sigconf,review]{acmart}` exactly as the call for papers
  requires, and is structured to mirror the ACM `sample-manuscript.tex`
  reference (CCS XML block, `ccsdesc`, keywords, `acks` environment,
  `\bibliography{refs}` with the ACM-Reference-Format style).
- `refs.bib` — bibliography database. Replaces the inline
  `\thebibliography` from the previous revision so that BibTeX is the
  single source of truth.
- `screencast_script.md` — timed shot list and voice-over for the
  ≤5-minute YouTube screencast.
- `acmart.cls`, `ACM-Reference-Format.bst`, `acmauthoryear.{bbx,cbx}`,
  `acmnumeric.{bbx,cbx}`, `acmdatamodel.dbx`, `acm-jdslogo.png` —
  vendored from the user-supplied Overleaf bundle. Do **not** edit.

## Build

Local build with TeX Live or MacTeX:

```bash
# From this directory:
latexmk -pdf -bibtex -interaction=nonstopmode paper.tex
```

Or step-by-step:

```bash
pdflatex paper
bibtex   paper
pdflatex paper
pdflatex paper
```

Overleaf: upload the entire `paper/` directory (or
`AI_Aware_Threat_Library_ACM.zip` plus `paper.tex`, `refs.bib`,
`screencast_script.md`); set the main document to `paper.tex` and the
compiler to `pdfLaTeX`.

## Page-fit checklist

The track caps demonstration papers at **four pages including all text,
references, and figures**. The current draft slots into:

| Section                | ~ pages |
| ---------------------- | ------- |
| Title block + abstract | 0.5     |
| 1 Introduction         | 0.5     |
| 2 Artifact overview    | 0.9     |
| 3 Annotated library    | 0.9     |
| 4 Usage scenarios      | 0.5     |
| 5 Evaluation evidence  | 0.3     |
| 6 Related work         | 0.2     |
| 7 Availability         | 0.2     |
| References             | inline  |
| **Total**              | ≈ 4.0   |

If the compiled PDF overflows the cap, the cheapest cuts (in order)
are: (i) drop Listing 1 (the schema excerpt); (ii) collapse Scenario B
into Scenario C; (iii) merge the *Limitations* paragraph in Section 5
into Section 7. The argument survives all three.

## Submission checklist

- [ ] LaTeX builds cleanly with `\documentclass[sigconf,review]{acmart}`.
- [ ] All `<USER>`, `XXXXXXX`, and `XXXXXXXXXXX` placeholders replaced
      with the final repository URL, Zenodo DOI, and YouTube identifier.
- [ ] CCS classifier values regenerated from
      <https://dl.acm.org/ccs> and pasted in place of the placeholders.
- [ ] PDF size within HotCRP limit; embedded fonts only.
- [ ] Screencast uploaded to YouTube and reachable from the abstract.
- [ ] Code repository public, `LICENSE` present, `README.md` carries the
      *Try it in 60 seconds* block.
- [ ] HotCRP "Connection with research track" question answered.
- [ ] `CITATION.cff` updated with the final Zenodo DOI.
