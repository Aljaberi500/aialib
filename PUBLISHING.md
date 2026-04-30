# Publishing `aialib`

This walkthrough takes the contents of this folder and turns them into a
public GitHub repository, a Zenodo-archived release with a citable DOI, a
prebuilt Docker image, and the YouTube-hosted screencast that the ASE 2026
call for papers requires.

Estimated end-to-end time: **about an hour**, mostly waiting on Zenodo to
reflect the GitHub release. Do all of the steps before submitting to HotCRP.

---

## 0. Prerequisites

- A GitHub account. Replace every occurrence of `<USER>` below with your
  GitHub handle.
- The GitHub CLI installed and authenticated: `gh auth login`. (If you do
  not want the CLI, every command has a Web UI equivalent — see the boxed
  notes.)
- `git` installed locally.
- A Zenodo account (free) with the same email you use on GitHub. Sign in
  at <https://zenodo.org/login/>.
- Optional but strongly recommended: Docker installed locally so you can
  publish a prebuilt image to GitHub Container Registry.

---

## 1. Initialize the local Git repository

From this folder (`github-release/`):

```bash
cd "/c/Users/PC/Documents/Claude/Projects/ASE Conf/github-release"
git init -b main
git add .
git commit -m "Initial public release of aialib v0.1.0"
```

Sanity check before pushing — every one of these greps must come back
empty:

```bash
git grep -nE 'aithreat|ai-threat-prototype|ai-threat-library-prototype' || echo "OK: no old names"
git grep -nE '/home/[a-z]|/Users/[a-z]'                               || echo "OK: no leaked paths"
git grep -nE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}' || echo "OK: no real secrets"
```

The `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `K2THINK_API_KEY` strings
are the names of environment variables, not actual keys, and are expected.

---

## 2. Create the GitHub repository and push

```bash
gh repo create aialib --public \
  --description "Reproducible AI-aware threat library and pipeline for LLM-generated code" \
  --homepage "https://github.com/<USER>/aialib"

git remote add origin "https://github.com/<USER>/aialib.git"
git push -u origin main
```

> **Web alternative.** Go to <https://github.com/new>, enter `aialib`,
> select **Public**, leave the *Initialize this repository* section
> empty (so the local commit is preserved), then click *Create
> repository* and follow the *push an existing repository* instructions
> the page shows.

After pushing, set the GitHub repository topics so it surfaces in search:

```bash
gh repo edit --add-topic llm,security,vulnerability-dataset,static-analysis,mitre-atlas,ci-cd
```

---

## 3. Replace placeholders in repository files

Several files contain `<USER>` and DOI placeholders. Resolve them before
tagging the release.

```bash
USER="<your-github-handle>"
sed -i "s|<USER>|${USER}|g" \
  README.md CITATION.cff pyproject.toml \
  paper/paper.tex paper/screencast_script.md
git commit -am "Set GitHub user in URLs"
git push
```

The `XXXXXXX` Zenodo DOI placeholder and the `XXXXXXXXXXX` YouTube
identifier are filled in **after** tagging the release (Sections 5 and
6 below), because Zenodo and YouTube only mint identifiers once the
artifact exists.

---

## 4. Publish a Docker image to GitHub Container Registry

Reviewers love a one-command demo. GitHub Container Registry (GHCR) is
free for public images.

```bash
echo "$GH_TOKEN" | docker login ghcr.io -u "<USER>" --password-stdin
docker build -t "ghcr.io/<USER>/aialib:0.1.0" -t "ghcr.io/<USER>/aialib:latest" .
docker push "ghcr.io/<USER>/aialib:0.1.0"
docker push "ghcr.io/<USER>/aialib:latest"
```

`$GH_TOKEN` is a personal access token with the `write:packages` scope
(<https://github.com/settings/tokens?type=beta>). After pushing,
go to the package page on GitHub, click *Package settings*, change the
visibility to **Public**, and link the package to the `aialib`
repository.

Update the README to reference the prebuilt image. The relevant Docker
block is around line 36 of `README.md`:

```bash
# Replace local-build instruction with prebuilt pull
docker run --rm -v "$PWD/out:/app/out" ghcr.io/<USER>/aialib:0.1.0
```

Commit and push the README change.

---

## 5. Connect Zenodo and tag the v0.1.0 release

This is the step that mints your citable DOI.

1. Go to <https://zenodo.org/account/settings/github/>. You will see a
   list of your GitHub repositories. Toggle `aialib` to **On**. Zenodo
   now watches the repository for releases.
2. Tag and push the release:

   ```bash
   git tag -a v0.1.0 -m "aialib v0.1.0 - ASE 2026 Tools and Datasets Track submission"
   git push origin v0.1.0
   ```

3. Cut the GitHub release. Either:

   ```bash
   gh release create v0.1.0 \
     --title "aialib v0.1.0" \
     --notes "$(cat <<'EOF'
   First public release.

   - Reproducible generator-detector-annotator pipeline (`make run`, `docker run`).
   - 504 annotated findings across four LLM providers (sample_outputs/threat_library.{csv,sqlite,sarif}).
   - JSON Schema, validation reports, ATLAS-aligned mappings.
   - Apache-2.0 (code) / CC BY 4.0 (dataset).
   EOF
   )"
   ```

   ...or use the *Releases* tab on GitHub and paste the same notes.

4. Within a minute or two, refresh
   <https://zenodo.org/account/settings/github/> — `aialib` will now show
   a DOI under its name (something like `10.5281/zenodo.1234567`). Copy
   the DOI **without** any `https://` prefix.

5. Replace the DOI placeholder in three files:

   ```bash
   DOI="10.5281/zenodo.1234567"
   sed -i "s|10\.5281/zenodo\.XXXXXXX|${DOI}|g" \
     README.md CITATION.cff paper/paper.tex paper/screencast_script.md
   git commit -am "Fill in Zenodo DOI for v0.1.0"
   git push
   ```

The DOI is now part of the repository on `main` and the released tarball
on Zenodo. GitHub's *Cite this repository* button (top-right of the repo
page) will pick up the updated `CITATION.cff` automatically.

---

## 6. Record and upload the screencast

Follow `paper/screencast_script.md`. Recording tips:

- Record in `1920x1080`, terminal font ≥ 16 pt, browser zoom 110 %.
- Do every step against the **published v0.1.0 image** (so what reviewers
  see is exactly what they get).
- Voice-over after the visuals are timed; three takes per shot is normal.

When the video is rendered:

1. Upload to YouTube as **Unlisted** (the call for papers does not
   require Public visibility, only "available by the time of submission";
   Unlisted is enough and reduces the risk of accidental edits in
   public). Do not enable monetization. Add `aialib`, `LLM security`,
   and `ASE 2026` as tags.
2. Copy the eleven-character video ID from the URL
   (`https://youtu.be/XXXXXXXXXXX`).
3. Replace the placeholder in the abstract:

   ```bash
   YOUTUBE="ABCDEFGHIJK"
   sed -i "s|XXXXXXXXXXX|${YOUTUBE}|g" \
     README.md paper/paper.tex paper/screencast_script.md
   git commit -am "Link the published screencast"
   git push
   ```

If you ever re-record after acceptance, do **not** delete the original
URL — upload a v2 separately and update the camera-ready paper.

---

## 7. Final repository polish

The following are optional but reviewer-positive:

- **Pin the repository** on your GitHub profile so it appears at the
  top of `github.com/<USER>`.
- **Enable GitHub Pages** from `docs/` so `codebase-overview.md` is
  rendered as a hosted site:

  ```bash
  gh repo edit --enable-pages --pages-branch main --pages-path /docs
  ```

- **Enable Discussions** for community Q&A:

  ```bash
  gh repo edit --enable-discussions
  ```

- **Add a "Cite this repository" check.** Visit the repository home
  page; there should be a *Cite this repository* button in the right
  sidebar that pulls from `CITATION.cff`. If it does not appear, lint
  the file with <https://citation-file-format.github.io/cff-converter-online/>.

---

## 8. Pre-submission checklist (HotCRP, by May 11)

Before you click *Submit* on
<https://ase26-tools-datasets.hotcrp.com/>, confirm every box:

- [ ] Repository public at `https://github.com/<USER>/aialib`.
- [ ] `LICENSE`, `NOTICE`, `CITATION.cff`, `CONTRIBUTING.md` present.
- [ ] README "Try it in 60 seconds" command works on a fresh machine.
- [ ] `make run` reproduces the bundled `sample_outputs/` row-for-row
      from a clean clone.
- [ ] Zenodo DOI minted for `v0.1.0`; DOI written into `README.md`,
      `CITATION.cff`, and `paper/paper.tex`.
- [ ] Docker image `ghcr.io/<USER>/aialib:0.1.0` public and pullable.
- [ ] Screencast on YouTube; URL written into the paper abstract and
      `screencast_script.md`.
- [ ] LaTeX builds cleanly:
      `cd paper && latexmk -pdf -bibtex paper.tex`.
- [ ] PDF is **four pages or fewer** with `\documentclass[sigconf,review]{acmart}`.
- [ ] CCS classifier values regenerated from
      <https://dl.acm.org/ccs> (the placeholders in `paper.tex` are
      labelled with `Software safety`, `Software security engineering`,
      and `Natural language generation` for guidance only).
- [ ] All `<USER>`, DOI, and YouTube placeholders resolved everywhere
      (`git grep -nE 'XXXXXXX|XXXXXXXXXXX|<USER>'` returns empty).
- [ ] HotCRP "Connection with research track" question answered (you
      have an accompanying thesis but no co-submitted research-track
      paper, so the answer is *No*).

---

## 9. Post-acceptance camera-ready notes

Accepted papers may revise the paper, screencast, code, and dataset by
the camera-ready deadline.

- For paper updates, switch the document class to
  `\documentclass[sigconf]{acmart}` (drop `review`) and regenerate the
  CCS metadata.
- For screencast updates, upload as a new video and supersede the
  abstract URL; do not delete the original.
- For code or dataset updates, tag `v0.1.1` (or `v1.0.0` if breaking)
  and let Zenodo mint a new versioned DOI; the `CITATION.cff` should
  be updated to point at the new DOI but keep the v0.1.0 DOI listed
  under `identifiers:` so prior citations remain resolvable.

---

## Quick reference — files that contain placeholders

| Placeholder | Files |
| ----------- | ----- |
| `<USER>`            | `README.md`, `CITATION.cff`, `pyproject.toml`, `paper/paper.tex`, `paper/screencast_script.md` |
| `XXXXXXX` (Zenodo)  | `README.md`, `CITATION.cff`, `paper/paper.tex`, `paper/screencast_script.md` |
| `XXXXXXXXXXX` (YouTube) | `README.md`, `paper/paper.tex`, `paper/screencast_script.md` |
| `0000-0000-0000-0000` (ORCID) | `paper/paper.tex` (drop the line if you do not have an ORCID) |
| CCS XML placeholders | `paper/paper.tex` |
