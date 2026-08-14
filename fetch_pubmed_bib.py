"""
fetch_pubmed_bib.py

自動從 PubMed 抓取指定作者的著作,轉成 BibTeX (.bib) 檔案。
設計給 GitHub Actions 定期執行 (見同目錄下的 update-pubs.yml)。

使用方式(本機測試,非必要):
    pip install requests
    python fetch_pubmed_bib.py
"""

import re
import time
import xml.etree.ElementTree as ET

import requests

# ---------------------------------------------------------------------------
# 這裡是你唯一需要自行調整的三個設定
# ---------------------------------------------------------------------------

# PubMed 搜尋語法。目前設定為排除同名作者:
# 只抓 Kuo SH 且 (單位是 Columbia) 或 (主題與 ataxia/tremor/cerebellum 相關) 的文章。
QUERY = (
    'Kuo SH[Author] AND '
    '(Columbia[Affiliation] OR ataxia[Title/Abstract] '
    'OR tremor[Title/Abstract] OR cerebellum[Title/Abstract])'
)

# NCBI 要求提供聯絡 email(不會公開顯示,只用於 NCBI 內部監控 API 流量)
EMAIL = "jouyenlin@gmail.com"  # <-- 請改成你自己的 email

# 輸出的 .bib 檔名,會存在 repo 根目錄
OUTPUT_FILE = "kuo_sh.bib"

# ---------------------------------------------------------------------------

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def get_pmids(query: str) -> list[str]:
    """向 PubMed 查詢符合條件的所有文章 PMID"""
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
    """依 PMID 批次抓取詳細書目資料(作者、標題、期刊、年份等)"""
    if not pmids:
        return []

    articles = []
    batch_size = 200  # 避免單次請求過大,分批抓取

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
                print(f"跳過一篇文章,解析錯誤: {e}")

        time.sleep(0.4)  # 禮貌性延遲,避免對 NCBI API 造成過大負擔

    return articles


def to_bibtex(articles: list[dict]) -> str:
    """把文章清單轉成 BibTeX 格式字串"""
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
    print(f"查詢 PubMed: {QUERY}")
    pmids = get_pmids(QUERY)
    print(f"找到 {len(pmids)} 篇文章 (PMID)")

    articles = fetch_details(pmids)
    print(f"成功解析 {len(articles)} 筆書目資料")

    bib = to_bibtex(articles)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(bib)

    print(f"已寫入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
