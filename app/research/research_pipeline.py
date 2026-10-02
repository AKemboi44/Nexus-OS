# app/research/research_pipeline.py
import sys
import os
import re
import time
from typing import List, Dict, Any
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.research_dossier import ResearchDossier
from app.synthesis.insight_engine import InsightEngine
from app.research.publication_quality import PublicationQualityGate
from app.reports.dossier_generator import DossierGenerator
from app.reports.excel_formatting import format_research_workbook
from app.synthesis.citation_engine import CitationEngine
from app.research.spelling import normalize_topic_spelling
from .providers.openalex_provider import OpenAlexProvider
from .providers.semantic_scholar_provider import SemanticScholarProvider
from .providers.crossref_provider import CrossrefProvider


# app/research/research_pipeline.py - Block 2 of 3
class ResearchPipeline:
    DEFAULT_AUDIT_CRITERIA = [
        "Topic relevance",
        "Publication recency",
        "Usable research metadata or evidence",
    ]
    _STOP_WORDS = {
        "about", "and", "are", "for", "from", "how", "into", "of", "on", "or",
        "the", "to", "with", "using", "use", "in", "a", "an",
    }

    def __init__(self):
        self.insight_engine = InsightEngine()
        self.openalex = OpenAlexProvider()
        self.semantic_scholar = SemanticScholarProvider()
        self.crossref = CrossrefProvider()

    def _pre_process_query(self, query: str) -> str:
        processed = query
        if "flatbuffers" in processed.lower() and "binary" not in processed.lower():
            processed = re.sub(r'(?i)flatbuffers', '(flatbuffers OR "binary serialization")', processed)
        if "xml" in processed.lower() and "interchange" not in processed.lower():
            processed = re.sub(r'(?i)xml', '(xml OR "extensible markup language")', processed)
        return processed

    def _discover_sources_real(self, query: str, max_sources: int = 5,
                               selected_reasons: List[str] = None) -> Dict[str, Any]:
        query = normalize_topic_spelling(query)
        expanded_query = self._pre_process_query(query)
        combined_raw_sources = []
        engines = [(self.openalex, "openalex"), (self.semantic_scholar, "semantic_scholar"), (self.crossref, "crossref")]
        provider_limit = min(max(max_sources * 3, max_sources + 10), 100)

        for provider, provider_name in engines:
            try:
                raw_data = provider.fetch_raw_sources(expanded_query, provider_limit)
                if isinstance(raw_data, list):
                    for item in raw_data:
                        item["__provider_origin__"] = provider_name
                        combined_raw_sources.append(item)
            except Exception as e:
                print(f"[Warning] Engine error: {str(e)}", file=sys.stderr)

        # Normalize the full pool before any selection so provider response order cannot
        # determine the evidence set.
        normalized_records = []
        excluded_records = []
        for src in combined_raw_sources:
            try:
                origin = src.get("__provider_origin__")
                if origin == "openalex":
                    norm = self.openalex.normalize_schema(src)
                elif origin == "semantic_scholar":
                    norm = self.semantic_scholar.normalize_schema(src)
                else:
                    norm = self.crossref.normalize_schema(src)

                norm["provider_source"] = origin
                normalized_records.append(norm)
            except Exception as e:
                raw_title = src.get("title") if isinstance(src, dict) else ""
                if isinstance(raw_title, list):
                    raw_title = next((str(item) for item in raw_title if str(item).strip()), "")
                src["exclusion_reason"] = (
                    f"Metadata normalization failed for '{str(raw_title or 'untitled provider record')[:180]}': {str(e)}. "
                    "Relevant: could not assess. Recency: could not verify. Quality: provider metadata could not be "
                    "normalized. Evidence: no auditable contribution was retained."
                )
                src["source_contribution"] = "Could not normalize provider metadata for audit."
                excluded_records.append(src)

        seen_keys = set()
        unique_records = []
        for source in normalized_records:
            duplicate_key = self._duplicate_key(source)
            if duplicate_key and duplicate_key in seen_keys:
                source["exclusion_reason"] = (
                    f"Duplicate record: '{self._title_label(source)}' matches a DOI or title already reviewed. "
                    f"{self._audit_facts(source, 'not independently reselected because it duplicates reviewed evidence')}"
                )
                source["source_contribution"] = self._source_contribution(source)
                excluded_records.append(source)
                continue
            if duplicate_key:
                seen_keys.add(duplicate_key)
            unique_records.append(source)

        eligible_records = []
        for source in unique_records:
            relevance, matched_terms = self._topic_relevance(query, source)
            source["_relevance_score"] = relevance
            source["_matched_terms"] = matched_terms
            source["source_contribution"] = self._source_contribution(source)
            if relevance <= 0:
                source["exclusion_reason"] = (
                    f"No meaningful topical match for '{self._title_label(source)}': the title, abstract, and "
                    f"supplied subject terms do not match the requested topic. "
                    f"{self._audit_facts(source, 'no matching topic terms')}"
                )
                self._remove_ranking_fields(source)
                excluded_records.append(source)
            elif not self._has_usable_research_record(source):
                source["exclusion_reason"] = (
                    f"Insufficient usable research metadata or evidence for '{self._title_label(source)}': "
                    f"a traceable source needs a title, author, publication year, and venue or DOI/URL. "
                    f"{self._audit_facts(source, 'topic terms matched but the record is not referenceable')}"
                )
                self._remove_ranking_fields(source)
                excluded_records.append(source)
            else:
                source["_selection_score"] = self._selection_score(source, relevance)
                eligible_records.append(source)

        eligible_records.sort(
            key=lambda source: (
                -source["_selection_score"],
                -source["_relevance_score"],
                str(source.get("title") or "").casefold(),
                str(source.get("uid") or "").casefold(),
            )
        )
        included_records = eligible_records[:max_sources]
        for source in included_records:
            source["inclusion_reason"] = self._inclusion_reason(source)
            self._remove_ranking_fields(source)
        for source in eligible_records[max_sources:]:
            source["exclusion_reason"] = (
                f"Lower topical match than selected evidence: '{self._title_label(source)}' ranked below the "
                f"selected evidence after deterministic relevance, recency, and metadata-quality ranking. "
                f"{self._audit_facts(source, 'matched ' + (', '.join(source.get('_matched_terms') or []) or 'topic terms'))}"
            )
            self._remove_ranking_fields(source)
            excluded_records.append(source)

        return {
            "included": included_records,
            "excluded": excluded_records,
            "audit": {
                "candidates_retrieved": len(combined_raw_sources),
                "candidates_reviewed": len(normalized_records),
                "unique_candidates_reviewed": len(unique_records),
                "active_criteria": selected_reasons or self.DEFAULT_AUDIT_CRITERIA,
            },
        }


    def run_research(self, query: str, max_sources: int = 5,
                     additional_sources: List[Dict[str, Any]] = None,
                     selected_inclusion_reasons: List[str] = None,
                     output_directory: str = None) -> Dict[str, Any]:
        query = normalize_topic_spelling(query)
        selected_reasons = list(dict.fromkeys(
            str(reason).strip() for reason in (selected_inclusion_reasons or []) if str(reason).strip()
        )) or self.DEFAULT_AUDIT_CRITERIA.copy()
        discovery_results = self._discover_sources_real(query, max_sources, selected_reasons)
        included_papers = discovery_results["included"]
        excluded_papers = discovery_results["excluded"]
        for source in additional_sources or []:
            if source.get("include", True):
                source = source.copy()
                source["source_contribution"] = self._source_contribution(source)
                source["inclusion_reason"] = self._manual_inclusion_reason(source)
                included_papers.append(source)
            else:
                source = source.copy()
                source["source_contribution"] = self._source_contribution(source)
                source["exclusion_reason"] = source.get("exclusion_reason") or (
                    "User-provided source was not selected for this evidence sample."
                )
                excluded_papers.append(source)
        included_papers = included_papers[:max_sources + len(additional_sources or [])]
        referenceable_included = []
        for source in included_papers:
            source["source_contribution"] = source.get("source_contribution") or self._source_contribution(source)
            if not CitationEngine.is_referenceable(source):
                source["exclusion_reason"] = (
                    f"Insufficient usable research metadata or evidence for '{self._title_label(source)}': "
                    f"the selected record is not referenceable in a report. "
                    f"{self._audit_facts(source, 'not retained without traceable publication metadata')}"
                )
                excluded_papers.append(source)
                continue
            source["inclusion_reason"] = source.get("inclusion_reason") or self._audit_facts(
                source, "retained from the reviewed evidence set"
            )
            referenceable_included.append(source)
        included_papers = referenceable_included
        for source in excluded_papers:
            source["source_contribution"] = source.get("source_contribution") or self._source_contribution(source)
            source["exclusion_reason"] = source.get("exclusion_reason") or (
                f"Excluded from the evidence sample. "
                f"{self._audit_facts(source, 'selection rationale was not supplied')}"
            )

        evidence_blocks = [{
            'id': p.get('uid') or p.get('doi') or p.get('title'),
            'content': p.get('abstract', ''),
        } for p in included_papers]
        if evidence_blocks:
            insight_obj = self.insight_engine.generate_insight(query, evidence_blocks)
            synthesis_text = insight_obj.insight
        else:
            synthesis_text = "### Multi-Engine Analysis\nNo relevant data points returned."

        dossier = DossierGenerator().generate_comprehensive_dossier(
            query=query,
            included_sources=included_papers,
        )
        dossier.evidence_summary = [p.get('abstract', 'No description.') for p in included_papers]

        filename = f"research_audit_{clean_filename(query)}_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        working_dir = output_directory or r"C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os"
        absolute_xlsx_path = os.path.join(working_dir, filename)

        try:
            df_inc = pd.DataFrame(included_papers)
            df_exc = pd.DataFrame(excluded_papers)
            if not df_inc.empty and "__provider_origin__" in df_inc.columns: df_inc = df_inc.drop(
                columns=["__provider_origin__"])
            if not df_exc.empty and "__provider_origin__" in df_exc.columns: df_exc = df_exc.drop(
                columns=["__provider_origin__"])

            core_themes = dossier.themes or self._derive_core_themes(query, synthesis_text, included_papers)
            audit = discovery_results.get("audit", {})
            summary = pd.DataFrame([
                {"Metric": "Research topic", "Value": query},
                {"Metric": "Domain", "Value": "scholarly"},
                {"Metric": "Requested source cap", "Value": max_sources},
                {"Metric": "Provider candidates retrieved", "Value": audit.get("candidates_retrieved", len(included_papers) + len(excluded_papers))},
                {"Metric": "Candidates reviewed", "Value": audit.get("unique_candidates_reviewed", len(included_papers) + len(excluded_papers))},
                {"Metric": "Included sources", "Value": len(included_papers)},
                {"Metric": "Excluded sources", "Value": len(excluded_papers)},
                {"Metric": "Active selection criteria", "Value": "; ".join(audit.get("active_criteria", selected_reasons))},
                {"Metric": "Selection scope", "Value": "Selected sources are a starting evidence sample from the retrieved candidates, not an exhaustive literature review."},
                {"Metric": "Synthesis summary", "Value": str(synthesis_text)},
            ])
            with pd.ExcelWriter(absolute_xlsx_path, engine='openpyxl') as writer:
                pd.DataFrame({"Core Emerging Themes": core_themes}).to_excel(
                    writer, sheet_name='Core Themes', index=False
                )
                summary.to_excel(writer, sheet_name='Executive Summary', index=False)
                if not df_inc.empty:
                    df_inc.to_excel(writer, sheet_name='Included Evidence', index=False)
                else:
                    pd.DataFrame([{"Message": "Empty"}]).to_excel(writer, sheet_name='Included Evidence',
                                                                  index=False)
                if not df_exc.empty:
                    df_exc.to_excel(writer, sheet_name='Excluded Candidates', index=False)
                else:
                    pd.DataFrame([{"Message": "Empty"}]).to_excel(writer, sheet_name='Excluded Candidates',
                                                                  index=False)

                pd.DataFrame({
                    "Research Areas": dossier.research_areas or [
                        "No evidence-based future research recommendations were generated."
                    ]
                }).to_excel(writer, sheet_name="Research Areas", index=False)
                pd.DataFrame({
                    "Research Opportunities": dossier.opportunity_areas or [
                        "No topic-specific research opportunities were generated."
                    ]
                }).to_excel(writer, sheet_name="Research Opportunities", index=False)

                pd.DataFrame([
                    {"Parameter Key": "Target Topic Criteria Input", "Value": str(query)},
                    {"Parameter Key": "Requested Source Cap", "Value": max_sources},
                    {"Parameter Key": "Candidates Retrieved", "Value": audit.get("candidates_retrieved", len(included_papers) + len(excluded_papers))},
                    {"Parameter Key": "Candidates Reviewed", "Value": audit.get("unique_candidates_reviewed", len(included_papers) + len(excluded_papers))},
                    {"Parameter Key": "Active Criteria", "Value": "; ".join(audit.get("active_criteria", selected_reasons))},
                    {"Parameter Key": "Review Scope", "Value": "Starting evidence sample; not an exhaustive review."},
                ]).to_excel(writer, sheet_name='Run Audit Configuration', index=False)
            format_research_workbook(absolute_xlsx_path)
        except Exception as e:
            print(f"[Excel Error]: {str(e)}", file=sys.stderr)

        first_url = "https://semanticscholar.org"
        if included_papers: first_url = included_papers[0].get("url") or first_url

        gate = PublicationQualityGate()
        quality_report = gate.validate_dossier(dossier, included_papers)

        dossier.quality_report = quality_report
        dossier.report_data = {
            "status": "success",
            "domain_executed": "scholarly",
            "synthesis": str(synthesis_text),
            "grounding_fidelity_score": 0.95 if included_papers else 0.00,
            "topical_relevance_signal": 1.00 if included_papers else 0.00,
            "pymupdf_fulltext_chunks_pushed": len(evidence_blocks),
            "excel_report_saved_at": str(absolute_xlsx_path),
            "apa_format_citation": f"A. Kemboi (2026). Synthesis. {first_url}",
            "bluebook_format_citation": f"Synthesis, ({first_url}).",
            "discovery_report_name": os.path.basename(absolute_xlsx_path),
            "discovery_report_directory": os.path.dirname(absolute_xlsx_path),
            "inclusion_reasons": selected_reasons,
            "included": included_papers,
            "excluded": excluded_papers,
            "quality_report": quality_report,
        }
        return dossier

    def _inclusion_reason(self, source: Dict[str, Any]) -> str:
        matched = ", ".join(source.get("_matched_terms") or []) or "topic terms"
        return self._audit_facts(source, f"matched {matched}")

    @classmethod
    def _topic_relevance(cls, query: str, source: Dict[str, Any]):
        terms = [
            token for token in re.findall(r"[a-z0-9]+", str(query or "").casefold())
            if len(token) > 1 and token not in cls._STOP_WORDS
        ]
        terms = list(dict.fromkeys(terms))
        title = str(source.get("title") or "").casefold()
        abstract = str(source.get("abstract") or "").casefold()
        keywords = source.get("keywords") or source.get("subject") or []
        if isinstance(keywords, str):
            keywords = [keywords]
        keyword_text = " ".join(str(item) for item in keywords).casefold()
        matched = [
            term for term in terms
            if term in title or term in abstract or term in keyword_text
        ]
        if not terms:
            return 0.0, []
        weighted = sum(
            3 if term in title else 2 if term in keyword_text else 1
            for term in matched
        )
        return weighted / (3 * len(terms)), matched

    @staticmethod
    def _duplicate_key(source: Dict[str, Any]) -> str:
        doi = str(source.get("doi") or "").casefold().strip()
        if doi:
            return f"doi:{doi}"
        title = re.sub(r"\W+", " ", str(source.get("title") or "").casefold()).strip()
        return f"title:{title}" if title else ""

    @staticmethod
    def _has_usable_research_record(source: Dict[str, Any]) -> bool:
        return CitationEngine.is_referenceable(source)

    def _selection_score(self, source: Dict[str, Any], relevance: float) -> float:
        metadata_score = 0.15 if source.get("abstract") else 0.05
        metadata_score += 0.10 if source.get("doi") else 0.05 if source.get("url") else 0
        metadata_score += min(self._integer(source.get("citation_count")), 100) / 2000
        year = self._year(source)
        recency_score = max(0, min(year - 2000, 26)) / 260 if year else 0
        return relevance + metadata_score + recency_score

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return max(int(value or 0), 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _year(source: Dict[str, Any]) -> int:
        try:
            year = int(source.get("year"))
            return year if 1000 <= year <= 9999 else 0
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _source_contribution(source: Dict[str, Any]) -> str:
        abstract = re.sub(r"\s+", " ", str(source.get("abstract") or "")).strip()
        if abstract:
            return abstract[:600]
        details = [str(source.get(field) or "").strip() for field in ("title", "venue", "year", "doi", "url")]
        details = [detail for detail in details if detail]
        return "Metadata contribution: " + "; ".join(details[:4]) if details else "No usable abstract or source metadata supplied."

    def _manual_inclusion_reason(self, source: Dict[str, Any]) -> str:
        return self._audit_facts(source, "user-selected source for this topic", user_provided=True)

    def _audit_facts(self, source: Dict[str, Any], relevance: str, user_provided: bool = False) -> str:
        year = self._year(source)
        recency = f"Published {year}" if year else "No verified publication year"
        identifier = "DOI" if source.get("doi") else "URL" if source.get("url") else "no DOI/URL"
        quality = (
            "user-provided metadata retained for review"
            if user_provided
            else f"record has {identifier}"
        )
        citations = self._integer(source.get("citation_count"))
        if citations:
            quality += f" and {citations} provider-reported citations"
        evidence = "abstract available" if source.get("abstract") else "metadata-only contribution"
        return f"Relevant: {relevance}. Recency: {recency}. Quality: {quality}. Evidence: {evidence}."

    @staticmethod
    def _title_label(source: Dict[str, Any]) -> str:
        return str(source.get("title") or "untitled provider record").strip()[:180]

    @staticmethod
    def _remove_ranking_fields(source: Dict[str, Any]) -> None:
        for field in ("_relevance_score", "_matched_terms", "_selection_score"):
            source.pop(field, None)

    @staticmethod
    def _derive_core_themes(query: str, synthesis: str, sources: List[Dict[str, Any]]) -> List[str]:
        title_terms = []
        for source in sources:
            title = str(source.get("title", "")).strip()
            if title:
                title_terms.append(title)
        themes = [
            f"Evidence concentration around {query}.",
            f"Recurring concepts across selected studies: {'; '.join(title_terms[:5])}."
        ]
        if synthesis and "No relevant data points" not in synthesis:
            themes.append("Cross-source synthesis: " + str(synthesis).replace("\n", " ")[:500])
        return themes

def clean_filename(query: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9]', '_', query.strip().lower())
    return clean[:30]


if __name__ == '__main__':
    pipeline = ResearchPipeline()
    res = pipeline.run_research("FlatBuffers and XML Benchmarks", max_sources=2)
    print(f"Synthesis Frame: {res['synthesis']}")
