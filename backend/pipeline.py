import html
import json
import re
import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
MEDLINEPLUS_SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
ADDITIONAL_HEALTH_SITES = (
    {
        "name": "Healthline",
        "search_url": "https://www.healthline.com/search?q={query}",
    },
    {
        "name": "WebMD",
        "search_url": "https://www.webmd.com/search?query={query}",
    },
    {
        "name": "Mayo Clinic",
        "search_url": "https://www.mayoclinic.org/search/search-results?q={query}",
    },
    {
        "name": "Johns Hopkins Medicine",
        "search_url": "https://www.hopkinsmedicine.org/search?query={query}",
    },
)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being",
    "but", "by", "can", "could", "did", "do", "does", "for", "from", "had",
    "has", "have", "how", "in", "into", "is", "it", "its", "may", "might",
    "of", "on", "or", "our", "should", "that", "the", "their", "there",
    "these", "this", "those", "to", "was", "were", "what", "when", "which",
    "while", "who", "will", "with", "would", "cause", "causes", "caused",
    "effect", "effects", "claim", "claims", "prove", "proves", "improve",
    "improves", "improved", "increase", "increases", "increased", "reduce",
    "reduces", "reduced", "prevent", "prevents", "benefit", "benefits",
}
NEGATION_CUES = (
    "no evidence", "no association", "not associated", "not linked",
    "no causal", "no link", "no relationship", "no effect", "not causal",
    "not related", "not cause", "does not", "do not", "did not", "failed to",
    "fails to", "not effective", "ineffective", "not increase", "not reduce",
    "not improve", "not support", "absence of",
)
SUPPORT_CUES = (
    "associated with", "linked to", "causes", "caused by", "increases",
    "increased risk", "reduces", "reduced risk", "effective", "improves",
    "prevents", "benefit", "supports", "recommended", "higher risk",
    "lower risk", "significant improvement",
)
CLAIM_NEGATION_CUES = (" not ", " never ", " no ", " without ", " isn't ", " aren't ")


class SourceSearchError(Exception):
    """Raised when the external biomedical literature service is unavailable."""


class MedicalFactCheckerPipeline:
    def _claim_terms(self, claim):
        words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", claim.lower())
        terms = [word for word in words if word not in STOP_WORDS]
        return list(dict.fromkeys(terms))[:6]

    def _search_sources(self, claim):
        terms = self._claim_terms(claim)
        if not terms:
            return []

        sources = []
        search_succeeded = False
        query = "TITLE_ABS:(" + " AND ".join(terms[:4]) + ") AND HAS_ABSTRACT:y"
        params = urlencode({
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": 15,
        })
        try:
            payload = self._request_json(f"{EUROPE_PMC_URL}?{params}")
            if payload.get("errCode") or "resultList" not in payload:
                raise SourceSearchError("Europe PMC returned an invalid search response.")
            sources.extend(self._europe_pmc_sources(payload))
            search_succeeded = True
        except SourceSearchError:
            pass

        try:
            sources.extend(self._search_pubmed(terms[:4]))
            search_succeeded = True
        except SourceSearchError:
            pass

        try:
            sources.extend(self._search_medlineplus(terms[:5]))
            search_succeeded = True
        except SourceSearchError:
            pass

        if not search_succeeded:
            raise SourceSearchError(
                "The biomedical literature services are temporarily unavailable. Please try again."
            )

        unique_sources = []
        seen = set()
        for source in sources:
            pmid = re.search(
                r"(?:article/MED/|pubmed\.ncbi\.nlm\.nih\.gov/)(\d+)",
                source["url"],
            )
            key = f"pmid:{pmid.group(1)}" if pmid else source["url"].rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                unique_sources.append(source)
        return unique_sources

    def _request_text(self, url):
        request = Request(
            url,
            headers={"User-Agent": "MedicalMythVerifier/1.0 (health claim evidence search)"},
        )
        for attempt in range(2):
            try:
                with urlopen(request, timeout=12) as response:
                    return response.read().decode("utf-8")
            except HTTPError as error:
                if (error.code < 500 and error.code != 429) or attempt == 1:
                    raise SourceSearchError("The biomedical literature request failed.") from error
            except (URLError, TimeoutError) as error:
                if attempt == 1:
                    raise SourceSearchError("The biomedical literature request failed.") from error
            time.sleep(0.5 * (attempt + 1))
        raise SourceSearchError("The biomedical literature request failed.")

    def _request_json(self, url):
        try:
            return json.loads(self._request_text(url))
        except (ValueError, TypeError) as error:
            raise SourceSearchError("The biomedical literature service returned invalid data.") from error

    def _europe_pmc_sources(self, payload):
        sources = []
        seen = set()
        for record in payload.get("resultList", {}).get("result", []):
            if record.get("source") != "MED":
                continue
            title = re.sub(r"<[^>]+>", "", record.get("title") or "").strip()
            abstract = re.sub(r"<[^>]+>", "", record.get("abstractText") or "").strip()
            source_id = record.get("pmid") or record.get("doi") or record.get("id")
            if not title or not abstract or not source_id or source_id in seen:
                continue
            seen.add(source_id)
            journal_info = record.get("journalInfo") or {}
            journal = journal_info.get("journal") or {}
            pmid = record.get("pmid")
            url = (
                f"https://europepmc.org/article/MED/{pmid}"
                if pmid else f"https://doi.org/{record['doi']}"
            )
            sources.append({
                "title": title,
                "journal": record.get("journalTitle") or journal.get("title") or "Biomedical journal",
                "year": record.get("pubYear"),
                "authors": record.get("authorString"),
                "url": url,
                "abstract": abstract,
                "provider": "Europe PMC",
            })
        return sources

    def _search_pubmed(self, terms):
        query = " AND ".join(f"{term}[Title/Abstract]" for term in terms)
        search_params = urlencode({
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": 15,
        })
        try:
            search = self._request_json(f"{PUBMED_ESEARCH_URL}?{search_params}")
            ids = search["esearchresult"]["idlist"]
        except (SourceSearchError, KeyError, TypeError) as error:
            raise SourceSearchError("PubMed search failed.") from error
        if not ids:
            return []

        fetch_params = urlencode({
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        })
        try:
            root = ET.fromstring(self._request_text(f"{PUBMED_EFETCH_URL}?{fetch_params}"))
        except (SourceSearchError, ET.ParseError) as error:
            raise SourceSearchError("PubMed article details could not be retrieved.") from error

        sources = []
        for article in root.findall(".//PubmedArticle"):
            article_node = article.find(".//Article")
            if article_node is None:
                continue
            title_node = article_node.find("ArticleTitle")
            abstract_parts = [
                "".join(part.itertext()).strip()
                for part in article_node.findall(".//Abstract/AbstractText")
            ]
            title = "".join(title_node.itertext()).strip() if title_node is not None else ""
            abstract = " ".join(part for part in abstract_parts if part)
            pmid = article.findtext(".//PMID")
            if not title or not abstract or not pmid:
                continue

            authors = []
            for author in article_node.findall(".//AuthorList/Author"):
                name = " ".join(
                    value for value in (
                        author.findtext("ForeName"),
                        author.findtext("LastName"),
                    ) if value
                )
                if name:
                    authors.append(name)
            year = (
                article_node.findtext(".//JournalIssue/PubDate/Year")
                or article_node.findtext(".//PubDate/Year")
            )
            if not year:
                medline_date = article_node.findtext(".//JournalIssue/PubDate/MedlineDate") or ""
                year_match = re.search(r"\b\d{4}\b", medline_date)
                year = year_match.group(0) if year_match else None
            sources.append({
                "title": title,
                "journal": article_node.findtext(".//Journal/Title") or "PubMed-indexed journal",
                "year": year,
                "authors": ", ".join(authors[:3]) or None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "abstract": abstract,
                "provider": "PubMed",
            })
        return sources

    def _search_medlineplus(self, terms):
        params = urlencode({
            "db": "healthTopics",
            "term": " ".join(terms),
            "retmax": 8,
        })
        try:
            root = ET.fromstring(self._request_text(f"{MEDLINEPLUS_SEARCH_URL}?{params}"))
        except (SourceSearchError, ET.ParseError) as error:
            raise SourceSearchError("MedlinePlus search failed.") from error

        sources = []
        for document in root.findall(".//document"):
            contents = {
                item.attrib.get("name"): "".join(item.itertext())
                for item in document.findall("content")
            }
            title = html.unescape(contents.get("title", ""))
            title = re.sub(r"<[^>]*>", "", title).strip()
            summary = html.unescape(contents.get("FullSummary", ""))
            summary = re.sub(r"<[^>]*>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()
            url = document.attrib.get("url")
            if not title or not summary or not url or not url.startswith("https://medlineplus.gov/"):
                continue
            sources.append({
                "title": title,
                "journal": contents.get("organizationName") or "MedlinePlus Health Topic",
                "year": None,
                "authors": None,
                "url": url,
                "abstract": summary,
                "provider": "MedlinePlus",
            })
        return sources

    def _evidence_for_source(self, source, claim_terms, claim_is_negative):
        sentences = re.split(r"(?<=[.!?])\s+", source["abstract"])
        relevant = []
        for sentence in sentences:
            words = set(re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", sentence.lower()))
            overlap = len(words.intersection(claim_terms))
            if overlap >= min(2, len(claim_terms)):
                relevant.append((overlap, sentence.strip()))

        if not relevant:
            return "unclear", ""

        sentence = max(relevant, key=lambda match: match[0])[1]
        normalized = f" {sentence.lower()} "
        has_negation = any(cue in normalized for cue in NEGATION_CUES)
        has_support = any(cue in normalized for cue in SUPPORT_CUES)
        if has_negation and not has_support:
            direction = "refutes" if not claim_is_negative else "supports"
        elif has_support and not has_negation:
            direction = "supports" if not claim_is_negative else "refutes"
        else:
            direction = "unclear"
        return direction, sentence

    def analyze_claim(self, claim_text):
        claim = claim_text.strip()
        if not claim:
            return {
                "claim": claim_text,
                "status": "Insufficient evidence",
                "fact_score": None,
                "myth_score": None,
                "sources": [],
                "evidence_count": 0,
                "summary": "Enter a health statement to search biomedical sources.",
            }

        sources = self._search_sources(claim)
        terms = self._claim_terms(claim)
        normalized_claim = f" {claim.lower()} "
        claim_is_negative = any(cue in normalized_claim for cue in CLAIM_NEGATION_CUES)
        evidence_sources = []
        counts = {"supports": 0, "refutes": 0, "unclear": 0}
        for source in sources:
            direction, excerpt = self._evidence_for_source(source, terms, claim_is_negative)
            counts[direction] += 1
            evidence_sources.append({
                key: value for key, value in source.items() if key != "abstract"
            } | {
                "direction": direction,
                "evidence": excerpt or "The source did not contain a directly matching evidence sentence.",
            })

        decisive = counts["supports"] + counts["refutes"]
        if decisive < 2:
            status = "Insufficient evidence"
            fact_score = None
            myth_score = None
            summary = (
                "The retrieved abstracts do not provide enough clear, directly relevant evidence "
                "to label this statement as a fact or a myth."
            )
        else:
            fact_score = round(100 * counts["supports"] / decisive)
            myth_score = 100 - fact_score
            if fact_score >= 70:
                status = "Likely fact"
            elif myth_score >= 70:
                status = "Likely myth"
            else:
                status = "Mixed evidence"
            summary = (
                f"Among {decisive} sources with a clear directional signal, "
                f"{counts['supports']} support and {counts['refutes']} contradict the statement. "
                "This is a source-agreement estimate, not a clinical diagnosis or a validated model probability."
            )

        return {
            "claim": claim,
            "status": status,
            "fact_score": fact_score,
            "myth_score": myth_score,
            "evidence_count": len(sources),
            "directional_source_count": decisive,
            "summary": summary,
            "sources": evidence_sources,
            "methodology": "Evidence is retrieved from PubMed/Europe PMC and MedlinePlus. Percentages count retrieved sources with directly matched sentences and explicit directional language.",
            "additional_site_searches": [
                {
                    "name": site["name"],
                    "url": site["search_url"].format(query=quote_plus(claim)),
                }
                for site in ADDITIONAL_HEALTH_SITES
            ],
        }

    def get_dashboard_metrics(self):
        return {
            "source": "Europe PMC",
            "source_url": "https://europepmc.org/",
            "description": "Searches biomedical journal literature for every submitted claim.",
        }
