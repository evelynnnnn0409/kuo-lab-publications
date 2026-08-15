"""
fetch_pubmed_bib.py

Automatically fetches a specific author's publications from PubMed and
writes them out as a BibTeX (.bib) file. Designed to be run on a schedule
by GitHub Actions (see update-pubs.yml in the same directory).

Manual local testing (optional, not required):
    pip install requests
    python fetch_pubmed_bib.py
"""

import re
import time
import xml.etree.ElementTree as ET

import requests

# ---------------------------------------------------------------------------
# SETTINGS — this is the only section you should need to edit
# ---------------------------------------------------------------------------

# --- Building block 1: how to recognize "this specific person" ------------
# PubMed stores author names two ways:
#   [Author]      -> always stored as "Lastname FI" (e.g. "Kuo SH")
#   [Full Author Name] -> full spelled-out name, "Lastname, Firstname"

AUTHOR_NAME = (
    'Kuo SH[Author] '
    'OR "Kuo, Sheng-Han"[Full Author Name]'
    'OR "Sheng-Han, Kuo"[Full Author Name]'
)

# Same idea, but for the separate "Investigator" (a.k.a. Collaborator) field.
# This field holds people credited as contributors to a large multi-site
# consortium study without being listed as a formal paper "Author".
INVESTIGATOR_NAME = (
    'Kuo SH[Investigator] '
    'OR "Kuo, Sheng-Han"[Full Investigator Name]'
    'OR "Sheng-Han, Kuo"[Full Investigator Name]'
)

# ORCID iD: a permanent, person-specific researcher identifier. If a paper
# has this ORCID attached, we trust it completely — no extra filtering needed.
ORCID = '0000-0002-9412-931X[auid]'

# --- Building block 2: how to confirm it's really THIS Dr. Kuo ------------
# Used to disambiguate from other people who share the same name.
# A paper counts if it matches ANY ONE of these (affiliation OR any topic).
TOPIC_OR_AFFILIATION = (
    ' "ataxia" [Title/Abstract]'
    'OR "Ataxia"[MeSH Terms] '
    'OR "tremor"[Title/Abstract] '
    'OR "Tremor"[MeSH Terms] '
    'OR "cerebellum"[Title/Abstract] '
    'OR "Cerebellum"[MeSH Terms] '
    'OR "dystonia"[Title/Abstract] '
    'OR "Dystonia"[MeSH Terms] '
    'OR "Parkinson"[Title/Abstract] '
    'OR "Parkinson Disease"[MeSH Terms] '
    'OR "movement disorder"[Title/Abstract] '
    'OR "Movement Disorders"[MeSH Terms] '
    'OR "Tourette"[Title/Abstract]'
    'OR "Tourette Syndrome"[MeSH Terms]'
    'OR "NeuroImage"[Title/Abstract]'
    'OR "Stroke"[MeSH Terms]'
    'OR "neurological"[Title/Abstract]'
    'OR "autistic"[Title/Abstract]'
    'OR "myoclonus"[Title/Abstract]'
    'OR "Neurons/metabolism" [MeSH Terms]'
    'OR "neuro-oncology"[Title/Abstract]'
    'OR "Alzheimer"[Title/Abstract]'
    'OR "Multiple System Atrophy"[Title/Abstract]'
    'OR "Restless legs syndrome"[Title/Abstract]'
    'OR "epilepticus"[Title/Abstract]'
)

# --- Final assembly: three independent branches, joined with OR -----------
# A paper is included if it matches ANY ONE of the three branches below:
#   Branch A: listed as a formal Author AND topic/affiliation checks out
#   Branch B: listed as an Investigator/Collaborator AND topic/affiliation checks out
#   Branch C: has the ORCID attached (trusted on its own, no extra AND needed)
QUERY = (
    f'(({AUTHOR_NAME}) AND ({TOPIC_OR_AFFILIATION})) '
    f'OR (({INVESTIGATOR_NAME}) AND ({TOPIC_OR_AFFILIATION})) '
    f'OR ({ORCID})'
)

# NCBI requires a contact email for API usage (not publicly displayed —
# only used by NCBI if they need to reach out about unusual traffic).
EMAIL = "jouyenlin@gmail.com"  # <-- change this to your real email

# Name of the output .bib file, written to the repo root.
OUTPUT_FILE = "kuo_sh.bib"

# ---------------------------------------------------------------------------

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def get_pmids(query: str) -> list[str]:
    """Query PubMed and return every PMID matching the search terms."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": 500,
        "email": EMAIL,
        "tool": "kuo-lab-bib-updater",
    }
    r = requests.get(ESEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def fetch_details(pmids: list[str]) -> list[dict]:
    """Fetch full bibliographic details (authors, title, journal, year, etc.)
    for a list of PMIDs, in batches."""
    if not pmids:
        return []

    articles = []
    batch_size = 200  # keep individual requests from getting too large

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "rettype": "abstract",
            "retmode": "xml",
            "email": EMAIL,
            "tool": "kuo-lab-bib-updater",
        }
        r = requests.get(EFETCH_URL, params=params, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        for article in root.findall(".//PubmedArticle"):
            try:
                pmid = article.findtext(".//PMID")
                title = article.findtext(".//ArticleTitle") or "No title"
                title = re.sub(r"[{}]", "", title).strip().rstrip(".")

                journal = (
                    article.findtext(".//Journal/Title")
                    or article.findtext(".//Journal/ISOAbbreviation")
                    or ""
                )

                year = article.findtext(".//JournalIssue/PubDate/Year")
                if not year:
                    medline_date = (
                        article.findtext(".//JournalIssue/PubDate/MedlineDate") or ""
                    )
                    year = medline_date[:4] if medline_date[:4].isdigit() else "n.d."

                volume = article.findtext(".//JournalIssue/Volume") or ""
                issue = article.findtext(".//JournalIssue/Issue") or ""
                pages = article.findtext(".//Pagination/MedlinePgn") or ""

                doi = ""
                for eid in article.findall(".//ELocationID"):
                    if eid.attrib.get("EIdType") == "doi":
                        doi = eid.text or ""

                authors = []
                for author in article.findall(".//AuthorList/Author"):
                    last = author.findtext("LastName")
                    fore = author.findtext("ForeName")
                    if last and fore:
                        authors.append(f"{last}, {fore}")
                    elif last:
                        authors.append(last)

                articles.append(
                    {
                        "pmid": pmid,
                        "title": title,
                        "journal": journal,
                        "year": year,
                        "volume": volume,
                        "issue": issue,
                        "pages": pages,
                        "doi": doi,
                        "authors": authors,
                    }
                )
            except Exception as e:
                print(f"Skipping one article due to a parsing error: {e}")

        time.sleep(0.4)  # be polite to the NCBI API, avoid hammering it

    return articles


def to_bibtex(articles: list[dict]) -> str:
    """Convert a list of article dicts into a BibTeX-formatted string."""
    entries = []
    for a in articles:
        key = f"pmid{a['pmid']}"
        authors_str = " and ".join(a["authors"]) if a["authors"] else "Unknown"

        fields = [
            f"  author = {{{authors_str}}}",
            f"  title = {{{a['title']}}}",
            f"  journal = {{{a['journal']}}}",
            f"  year = {{{a['year']}}}",
        ]
        if a["volume"]:
            fields.append(f"  volume = {{{a['volume']}}}")
        if a["issue"]:
            fields.append(f"  number = {{{a['issue']}}}")
        if a["pages"]:
            fields.append(f"  pages = {{{a['pages']}}}")
        if a["doi"]:
            fields.append(f"  doi = {{{a['doi']}}}")
        fields.append(f"  url = {{https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/}}")

        entry = f"@article{{{key},\n" + ",\n".join(fields) + "\n}\n"
        entries.append(entry)

    return "\n".join(entries)


def main():
    print(f"Querying PubMed: {QUERY}")
    pmids = get_pmids(QUERY)
    print(f"Found {len(pmids)} articles (PMIDs)")

    articles = fetch_details(pmids)
    print(f"Successfully parsed {len(articles)} bibliographic records")

    # Export BibTeX
    bib = to_bibtex(articles)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(bib)

    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
