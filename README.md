# Kuo Lab Publications — Automated PubMed Feed

This repository automatically keeps an up-to-date list of Dr. Sheng-Han Kuo's (Columbia University, Department of Neurology) publications, and feeds that list into a publications page on the lab website ([thekuolab.org](https://www.thekuolab.org/publications-1)).

## How it works

PubMed  --(weekly search)-->  fetch_pubmed_bib.py  --(writes)-->  kuo_sh.bib 
—> BibBase.org reads the .bib file and renders a formatted publication list —> Embedded on the lab website
                                                              
1. `fetch_pubmed_bib.py` queries the PubMed API (NCBI E-utilities) for Dr. Kuo's publications and writes the results to `kuo_sh.bib` in BibTeX format.
2. `.github/workflows/update-pubs.yml` runs that script automatically once a week (and can also be triggered manually), committing the updated `kuo_sh.bib` back to this repo.
3. [BibBase](https://bibbase.org) reads `kuo_sh.bib` directly from this repo (via its raw GitHub URL) and generates a formatted, filterable publication list, along with an embed snippet used on the lab website.

Because BibBase reads the file directly from GitHub, no one needs to manually re-upload anything — updating `kuo_sh.bib` here is enough for the website to catch up automatically (usually within 24 hours).

## Files

| File | Purpose |
|---|---|
| `fetch_pubmed_bib.py` | Queries PubMed and writes `kuo_sh.bib` |
| `.github/workflows/update-pubs.yml` | Runs the script on a weekly schedule via GitHub Actions |
| `kuo_sh.bib` | Auto-generated. The current publication list in BibTeX format. Do not edit by hand — it gets overwritten every run. |

## One-time setup

1. In **Settings → Actions → General → Workflow permissions**, select  **"Read and write permissions"**. This lets the scheduled job commit  the updated `.bib` file back to the repo.
2. Open `fetch_pubmed_bib.py` and set `EMAIL` to a real contact email  (required by NCBI's API usage policy; it is not publicly displayed  anywhere).
3. Go to the **Actions** tab → **Update PubMed Publications** →   **Run workflow** to trigger a first manual run and confirm it completes successfully.
4. Copy the **Raw** URL of `kuo_sh.bib` (button on the file's GitHub  page) and paste it into [bibbase.org](https://bibbase.org) to generate the publication list page and embed snippet.

## The search query, explained

Matching "Kuo SH" on PubMed is tricky because it's a common name shared by many unrelated researchers. The query in `fetch_pubmed_bib.py` is built from a few named building blocks so it's easier to read and edit:

- **`AUTHOR_NAME`** — matches the full spelled-out form (`Kuo, Sheng-Han`) in PubMed's formal "Author" field.
- **`INVESTIGATOR_NAME`** — same idea, but for PubMed's separate "Investigator" (a.k.a. Collaborator) field, used for people credited as contributors to large multi-site consortium studies without being listed as a formal paper author.
- **`ORCID`** — Dr. Kuo's permanent ORCID identifier (`0000-0002-9412-931X`). If a paper has this ORCID attached, it's trusted on its own with no further checks.
- **`TOPIC_OR_AFFILIATION`** — a set of specialty keywords (ataxia, tremor, cerebellum, dystonia, Parkinson, movement disorder, Tourette), used to help confirm a name match is really this Dr. Kuo and not someone els with the same name.

The final `QUERY` combines these with OR logic: a paper is included if
it matches *any* of (Author name + topic/affiliation), (Investigator
name + topic/affiliation), or (ORCID alone).

**Known limitation:** this is a best-effort heuristic, not a perfect filter. A paper can still be missed if it doesn't mention any of the listed keywords isn't yet MeSH-indexed. Because of this, it's worth periodically (e.g. once a quarter) spot-checking the publication count, and tightening the query if the counts drift apart.

## Updating the search terms

To add a new keyword or disease term, edit `TOPIC_OR_AFFILIATION` in `fetch_pubmed_bib.py`, then manually re-run the workflow from the **Actions** tab to confirm the change works before letting it run on its own schedule again.

## Changing the schedule

The run frequency is set in `.github/workflows/update-pubs.yml` via a [cron expression](https://crontab.guru/):
```yaml
schedule:
  - cron: '0 6 * * 1'   # every Monday at 06:00 UTC
```

## Troubleshooting a failed run

1. Go to **Actions** → click the failed run → click the failed step
   (marked with a red ✕) to expand its log.
2. Look for a Python traceback (a block of red text ending in a line
   like `SomeError: ...`) — that tells you the actual cause. A
   deprecation notice about Node.js versions in the same log is
   unrelated to the script and can be ignored.
3. Common causes: a typo introduced while editing the `QUERY` string
   (e.g. curly "smart quotes" from copy-pasting instead of straight
   `"` quotes), or a missing `EMAIL` value.
