# app/agents/scribe_agent.py - Part A
import os
import sys
import re
import time
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app.synthesis.citation_engine import CitationEngine
from app.research.publication_quality import PublicationQualityGate
from dotenv import load_dotenv


class ScribeResearchAgent:
    """
    Advanced Academic Drafting Agent (Post-MVP Engine)
    Generates structured Word documents with cohesive grouped citation patterns.
    """
    def __init__(self):
        self.client = None
        self._editorial_calls = 0
        self._editorial_cache = {}
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=api_key)
            except Exception as error:
                print(f"[Scribe Editorial Notice]: Gemini editor unavailable: {error}")

    def generate_apa_dossier_report(self, topic: str, included_sources: list,
                                    dossier=None, domain: str = "scholarly",
                                    output_directory: str = None) -> str:
        return self._generate_report(
            topic, included_sources, dossier=dossier, domain=domain,
            report_type="proposal", output_directory=output_directory
        )

    def generate_full_research_starter_report(self, topic: str, included_sources: list,
                                               dossier=None, domain: str = "scholarly",
                                               output_directory: str = None) -> str:
        return self.generate_complete_literature_review(
            topic, included_sources, dossier=dossier, domain=domain,
            output_directory=output_directory
        )

    def generate_complete_literature_review(self, topic: str, included_sources: list,
                                            dossier=None, domain: str = "scholarly",
                                            output_directory: str = None) -> str:
        return self._generate_report(
            topic, included_sources, dossier=dossier, domain=domain,
            report_type="full_starter", output_directory=output_directory
        )

    def _generate_report(self, topic: str, included_sources: list,
                         dossier=None, domain: str = "scholarly",
                         report_type: str = "proposal",
                         output_directory: str = None) -> str:
        doc = Document()

        # Configure standard academic 1-inch margins on all sides
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        # Enforce standard APA Times New Roman 12pt typography
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)
        style.paragraph_format.line_spacing = 2.0
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.first_line_indent = Inches(0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # 1. Inject Standard APA Cover Title Page Elements
        title_p = doc.add_paragraph()
        title_p.alignment = 1  # Center Alignment Block
        title_p.paragraph_format.space_before = Pt(120)

        report_title = (
            "Comprehensive Pre-Research Proposal Report"
            if report_type == "proposal"
            else "Complete Literature Review"
        )
        title_run = title_p.add_run(f"{report_title}:\n{topic.title()}\n")
        title_run.bold = True

        author_p = doc.add_paragraph()
        author_p.alignment = 1
        author_p.paragraph_format.space_before = Pt(24)
        author_p.add_run(
            "Abraham Kiptoo Kemboi\n"
            "Nexus Research AI Collective Core\n"
            "Post-MVP Automation Node Suite"
        )

        doc.add_page_break()
        return self._write_synthesis_body(
            doc, topic, included_sources, dossier=dossier, domain=domain,
            report_type=report_type, output_directory=output_directory
        )

    # app/agents/scribe_agent.py - Part B
    def _write_synthesis_body(self, doc: Document, topic: str, included_sources: list,
                              dossier=None, domain: str = "scholarly",
                              report_type: str = "proposal",
                              output_directory: str = None) -> str:
        # 2. Main Title Header (Heading 1 Level)
        h1 = doc.add_paragraph()
        h1.alignment = 1
        h1_run = h1.add_run(
            "Complete Literature Review and Research Synthesis"
            if report_type == "full_starter"
            else "Literature Review and Pre-Research Proposal Synthesis"
        )
        h1_run.bold = True
        h1.paragraph_format.space_after = Pt(18)

        abstract = getattr(dossier, "abstract", "") if dossier else ""
        if not abstract:
            abstract = (
                f"This report synthesizes {len(included_sources)} selected {domain} source(s) "
                f"concerning {topic}."
            )
        self._add_heading(doc, "Abstract")
        self._add_body_paragraph(doc, self._format_abstract(abstract, topic, included_sources))

        themes = getattr(dossier, "themes", []) if dossier else []
        contradictions = getattr(dossier, "contradictions", []) if dossier else []
        gaps = getattr(dossier, "research_gaps", []) if dossier else []
        opportunities = getattr(dossier, "opportunity_areas", []) if dossier else []
        problems = getattr(dossier, "problems_to_solve", []) if dossier else []

        if report_type == "full_starter":
            self._write_full_starter_sections(
                doc, topic, included_sources, themes, contradictions,
                gaps, opportunities, problems, domain
            )
        else:
            self._write_proposal_sections(
                doc, topic, included_sources, themes, contradictions,
                gaps, opportunities, problems
            )

        # 4. References Page Layout Module (Hanging Indent)
        doc.add_page_break()
        ref_h = doc.add_paragraph()
        ref_h.alignment = 1
        ref_h_run = ref_h.add_run("References")
        ref_h_run.bold = True
        ref_h.paragraph_format.space_after = Pt(12)

        for src in included_sources:
            ref_p = doc.add_paragraph()
            ref_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            ref_p.paragraph_format.line_spacing = 2.0
            ref_p.paragraph_format.space_after = Pt(0)
            ref_p.paragraph_format.left_indent = Inches(0.5)
            ref_p.paragraph_format.first_line_indent = Inches(-0.5)

            source_dict = src if isinstance(src, dict) else vars(src)
            ref_p.add_run(CitationEngine.generate_apa_7th(source_dict).replace("*", ""))

        gate = PublicationQualityGate()
        quality_report = (
            gate.validate_dossier(
                dossier, included_sources, report_type=report_type
            )
            if dossier
            else {"score": 0.8, "passed": True}
        )
        if not quality_report.get("passed", True):
            warning = doc.add_paragraph()
            warning.add_run(
                "Publication quality gate warning: the current synthesis is below minimum evidence quality threshold. "
                "Review the source set and supported claims before submission."
            )

        filename_docx = (
            f"{'comprehensive_pre_research_proposal_report' if report_type == 'proposal' else 'complete_literature_review'}_{self._clean_filename(topic)}_"
            f"{time.strftime('%Y%m%d_%H%M%S')}.docx"
        )
        target_docx_path = os.path.join(
            output_directory or r"C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os",
            filename_docx,
        )
        doc.save(target_docx_path)
        return target_docx_path

    @staticmethod
    def _add_heading(doc, text):
        heading = doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(0)
        heading.add_run(text).bold = True

    @staticmethod
    def _add_body_paragraph(doc, text):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.line_spacing = 2.0
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.first_line_indent = Inches(0)
        clean_text = (
            str(text)
            .replace("**", "")
            .replace("*", "")
            .replace("—", ",")
            .replace("–", "-")
            .strip()
        )
        paragraph.add_run(clean_text)

    def _write_proposal_sections(self, doc, topic, sources, themes,
                                 contradictions, gaps, opportunities, problems):
        sections = [
            ("Key Themes", themes),
            ("Contradictions and Boundary Conditions", contradictions),
            ("Research Gaps", gaps),
            ("Opportunity Areas", opportunities),
            ("Research Problems", problems),
        ]
        for heading, items in sections:
            unique_items = self._unique_items(items)
            if not unique_items:
                continue
            self._add_heading(doc, heading)
            for item in unique_items:
                self._add_body_paragraph(
                    doc,
                    self._evidence_paragraph(
                        item,
                        sources,
                        topic=topic,
                        section=heading,
                        report_type="proposal",
                    ),
                )
        self._add_heading(doc, "Proposed Contribution")
        contribution = (
            f"The proposed study of {topic} should explain the conditions under which the "
            "central pattern appears, differs, or fails. Its contribution should be stated "
            "as a researchable question linked to the documented gap rather than as a promise "
            "of predetermined results."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                contribution,
                sources,
                topic=topic,
                section="Proposed Contribution",
                report_type="proposal",
            ),
        )

    def _write_full_starter_sections(self, doc, topic, sources, themes,
                                     contradictions, gaps, opportunities, problems, domain):
        theme_groups = self._cluster_sources_by_theme(themes, sources)
        self._add_heading(doc, "Research Problem and Rationale")
        problem = problems[0] if problems else (
            f"The central research problem concerns how evidence about {topic} can be translated "
            "into reliable, context-sensitive practice."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                problem,
                sources,
                topic=topic,
                section="Research Problem and Rationale",
                report_type="full_starter",
            ),
        )

        unique_themes = self._unique_items(themes)
        if unique_themes:
            self._add_heading(doc, "Thematic Literature Review")
            for theme in unique_themes:
                theme_sources = theme_groups.get(theme, sources[:2])
                self._add_body_paragraph(
                    doc,
                    self._evidence_paragraph(
                        theme,
                        theme_sources or sources,
                        topic=topic,
                        section="Thematic Literature Review",
                        report_type="full_starter",
                    ),
                )
        unique_contradictions = self._unique_items(contradictions)
        if unique_contradictions:
            self._add_heading(doc, "Comparative Analysis and Boundary Conditions")
            for item in unique_contradictions:
                self._add_body_paragraph(
                    doc,
                    self._evidence_paragraph(
                        item,
                        self._sources_for_point(item, sources),
                        topic=topic,
                        section="Comparative Analysis and Boundary Conditions",
                        report_type="full_starter",
                    ),
                )
        unique_gaps = self._unique_items(gaps)
        if unique_gaps:
            self._add_heading(doc, "Research Gap and Contribution")
            for item in unique_gaps:
                self._add_body_paragraph(
                    doc,
                    self._evidence_paragraph(
                        item,
                        sources,
                        topic=topic,
                        section="Research Gap and Contribution",
                        report_type="full_starter",
                    ),
                )
        unique_opportunities = self._unique_items(opportunities)
        if unique_opportunities:
            self._add_heading(doc, "Implications and Opportunities")
            for item in unique_opportunities:
                self._add_body_paragraph(
                    doc,
                    self._evidence_paragraph(
                        item,
                        sources,
                        topic=topic,
                        section="Implications and Opportunities",
                        report_type="full_starter",
                    ),
                )

        self._add_heading(doc, "Research Objectives")
        objectives = (
            f"The literature indicates that a study of {topic} should first clarify the central "
            "constructs, identify the mechanisms linking them, and determine the conditions under "
            "which the reported relationships are likely to hold. These objectives translate the "
            "review into a coherent analytical program without assuming findings that have not yet "
            "been empirically collected."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                objectives,
                sources,
                topic=topic,
                section="Research Objectives",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Conceptual Framework")
        framework = (
            f"A conceptual framework for {topic} should connect the main explanatory factors "
            "identified in the literature to the outcomes they are expected to influence. The "
            "framework should distinguish direct effects, contextual moderators, and measurable "
            "outcomes so that competing explanations can be compared rather than treated as interchangeable."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                framework,
                sources,
                topic=topic,
                section="Conceptual Framework",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Methodology")
        methodology = (
            f"The reviewed evidence supports a methodology for studying {topic} that makes the "
            "population, setting, variables, comparison conditions, and outcome measures explicit. "
            "A transparent design should combine appropriate source selection with reproducible "
            "measurement and an analysis strategy capable of testing both recurring patterns and boundary conditions."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                methodology,
                sources,
                topic=topic,
                section="Methodology",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Data Collection")
        data_collection = (
            f"Data collection for {topic} should follow the constructs and comparison logic established "
            "by the conceptual framework. The study should define inclusion criteria, document the "
            "collection setting, protect data quality, and record the decisions that determine which "
            "observations can support the final analysis."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                data_collection,
                sources,
                topic=topic,
                section="Data Collection",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Synthesis Findings")
        findings = (
            f"Across the selected literature, the most defensible finding about {topic} is that "
            "the observed pattern is meaningful but conditional. Agreement across studies strengthens "
            "the central interpretation, whereas differences in design, context, and measurement "
            "limit the extent to which the result can be generalized without further validation."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                findings,
                sources,
                topic=topic,
                section="Synthesis Findings",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Discussion")
        discussion = (
            f"The discussion of {topic} should interpret the literature as a connected body of "
            "knowledge rather than as a sequence of isolated summaries. The strongest contribution "
            "comes from showing where studies converge, where they disagree, and how those differences "
            "define the next research decision."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                discussion,
                sources,
                topic=topic,
                section="Discussion",
                report_type="full_starter",
            ),
        )

        self._add_heading(doc, "Proposed Research Direction")
        direction = (
            f"A suitable {domain} study on {topic} should define its population, setting, explanatory variables, "
            "comparison conditions, and outcome measures before collecting additional evidence."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                direction,
                sources,
                topic=topic,
                section="Proposed Research Direction",
                report_type="full_starter",
            ),
        )
        self._add_heading(doc, "Operationalization and Study Design")
        design = (
            f"A full starter study on {topic} should operationalize its core constructs, "
            "identify comparison conditions, specify measurable outcomes, and document the "
            "sampling and analytical decisions needed for reproducible evaluation."
        )
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                design,
                sources,
                topic=topic,
                section="Operationalization and Study Design",
                report_type="full_starter",
            ),
        )
        self._add_heading(doc, "Conclusion")
        self._add_body_paragraph(
            doc,
            self._evidence_paragraph(
                f"Overall, the evidence suggests that {topic} remains important but is not adequately resolved by isolated findings.",
                sources,
                topic=topic,
                section="Conclusion",
                report_type="full_starter",
            ),
        )

    def _write_exhaustive_theme(self, doc, topic, theme, sources, conclusion):
        """Write one bounded paragraph for a theme; do not multiply stock prose."""
        self._add_body_paragraph(doc, self._evidence_paragraph(theme, sources))

    @staticmethod
    def _unique_items(items):
        seen = set()
        unique = []
        for item in items or []:
            text = re.sub(r"\s+", " ", str(item).strip())
            key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            if text and key and key not in seen:
                seen.add(key)
                unique.append(text)
        return unique

    def _evidence_paragraph(
        self,
        text,
        sources,
        topic="the research question",
        section="Synthesis",
        report_type="proposal",
    ):
        """Build one focused six-sentence paragraph with a centered inline citation."""
        claim = re.sub(r"\s+", " ", str(text).strip())
        claim = self._remove_parenthetical_years(claim)
        claim = claim.replace("###", "").replace("**", "").replace("...", ".")
        claim = claim.replace('"', "").replace("“", "").replace("”", "").strip(" .")
        if not claim:
            claim = f"The available evidence addresses {topic}"
        claim = self._complete_sentence(claim)
        claim = self._editorial_claim(claim, topic, section, sources)

        point_sources = self._sources_for_point(claim, sources)
        citation = self._citation_for_sources(point_sources)
        source_titles = [
            self._source_value(source, "title", "the selected studies")
            for source in point_sources[:2]
        ]
        source_label = "; ".join(str(title) for title in source_titles if title)
        if not source_label:
            source_label = "the selected studies"
        source_label = self._complete_sentence(source_label, terminal="").strip(" .")

        proposal_mode = report_type != "full_starter"
        lead = self._sentence(claim)
        evidence_sentence = (
            f"The evidence appears in {source_label}, situating the finding within a defined "
            "research context rather than presenting it as universal."
        )
        scope_sentence = (
            f"The claim remains limited to the source record's stated context, measures, "
            f"and outcomes in the {section.lower()} section."
        )
        if proposal_mode:
            implication_sentence = (
                f"For the proposed study of {topic}, this finding defines a focused "
                "research question."
            )
            limitation_sentence = (
                "Its interpretation remains conditional because the evidence does not establish "
                "universal transferability."
            )
            closing_sentence = (
                "The theme is therefore a testable proposition, not a universal conclusion."
            )
        else:
            implication_sentence = (
                f"For the complete literature review on {topic}, the finding clarifies how the "
                "literature can become a measurable construct."
            )
            limitation_sentence = (
                "Uncertainty remains around transferability, measurement, and the boundary "
                "between correlation and explanation."
            )
            closing_sentence = (
                "The theme therefore contributes one defined part of the literature review."
            )

        paragraph = " ".join(
            [
                lead,
                evidence_sentence,
                scope_sentence,
                citation,
                implication_sentence,
                limitation_sentence,
                closing_sentence,
            ]
        )
        return self._fit_sentence_paragraph(paragraph, minimum=75, maximum=None)

    @staticmethod
    def _remove_parenthetical_years(text):
        parts = []
        cursor = 0
        while cursor < len(text):
            opening = text.find("(", cursor)
            if opening < 0:
                parts.append(text[cursor:])
                break
            closing = text.find(")", opening + 1)
            if closing < 0:
                parts.append(text[cursor:])
                break
            parts.append(text[cursor:opening])
            contents = text[opening + 1:closing]
            tokens = contents.replace(",", " ").replace(";", " ").split()
            has_year = any(
                len(token) == 4
                and token.isdigit()
                and token.startswith(("19", "20"))
                for token in tokens
            )
            if not has_year:
                parts.append(text[opening:closing + 1])
            cursor = closing + 1
        cleaned = " ".join("".join(parts).split())
        for punctuation in ",.;!?":
            cleaned = cleaned.replace(f" {punctuation}", punctuation)
        return cleaned

    def _editorial_claim(self, claim, topic, section, sources):
        """Paraphrase a source-grounded claim into a researcher-led synthesis."""
        if not self.client or not sources:
            return claim
        cache_key = (claim, topic, section)
        if cache_key in self._editorial_cache:
            return self._editorial_cache[cache_key]
        if self._editorial_calls >= 5:
            return claim
        evidence = []
        for source in self._sources_for_point(claim, sources)[:3]:
            evidence.append({
                "title": self._source_value(source, "title", ""),
                "abstract": self._source_value(source, "abstract", ""),
                "year": self._source_value(source, "year", ""),
            })
        prompt = (
            "Act as a senior academic researcher writing an original literature review paragraph. "
            "Paraphrase and synthesize the claim; do not quote, copy phrases, or mention source titles. "
            "Use an analytical voice that explains agreement, disagreement, extension, or limitation. "
            "Return exactly two complete sentences, no bullets, no citations, and no ellipses. "
            f"Topic: {topic}\nSection: {section}\nClaim: {claim}\nEvidence: {evidence}"
        )
        try:
            self._editorial_calls += 1
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            rewritten = re.sub(r"\s+", " ", str(response.text or "").strip())
            rewritten = rewritten.replace("...", ".").replace('"', "")
            if len(rewritten.split()) >= 20 and rewritten.endswith((".", "!", "?")):
                self._editorial_cache[cache_key] = rewritten
                return rewritten
        except Exception as error:
            print(f"[Scribe Editorial Warning]: {error}")
        return claim

    def _format_abstract(self, text, topic, sources):
        """Preserve a generated abstract as connected prose and normalize its keyword line."""
        clean = re.sub(r"\s+", " ", str(text or "").strip())
        clean = re.sub(r"^(?:abstract\s*:?)\s*", "", clean, flags=re.I)
        keyword_position = self._keyword_label_position(clean)
        if keyword_position is not None:
            body = clean[:keyword_position].strip(" .")
            keywords = clean[keyword_position:].split(":", 1)[1].strip(" .")
        else:
            body = clean.strip(" .")
            keyword_tokens = [
                token for token in self._content_tokens(topic)
                if len(token) > 3
            ][:5]
            keywords = ", ".join(keyword_tokens + ["evidence synthesis", "research methods"])

        if not body:
            body = (
                f"This review examines {topic} through a structured synthesis of the selected evidence. "
                "It identifies recurring findings, methodological differences, and unresolved research gaps."
            )
        if len(body.split()) < 100:
            body = (
                f"{body}. The review compares the settings, populations, measures, and outcomes represented "
                "in the source base, distinguishing recurring findings from claims that remain conditional. "
                "It also identifies practical implications and limitations that should guide subsequent study design. "
                "This structure links the evidence base to a coherent research problem while preserving the "
                "distinction between established findings, plausible interpretations, and questions requiring "
                "additional empirical validation."
            )
        return f"{body.strip(' .')}. Keywords: {keywords}."

    @staticmethod
    def _keyword_label_position(text):
        lowered = text.lower()
        cursor = 0
        while True:
            position = lowered.find("keyword", cursor)
            if position < 0:
                return None
            cursor = position + len("keyword")
            if position and (lowered[position - 1].isalnum() or lowered[position - 1] == "_"):
                continue
            label_end = cursor
            if label_end < len(lowered) and lowered[label_end] == "s":
                label_end += 1
            while label_end < len(lowered) and lowered[label_end].isspace():
                label_end += 1
            if label_end < len(lowered) and lowered[label_end] == ":":
                return position

    @staticmethod
    def _sentence(text):
        sentence = re.sub(r"\s+", " ", str(text).strip()).replace("...", ".").strip(" .")
        if not sentence:
            return "The available evidence identifies a bounded research pattern"
        return sentence[0].upper() + sentence[1:] + "."

    @staticmethod
    def _fit_sentence_paragraph(paragraph, minimum=75, maximum=None):
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph.strip()) if part.strip()]
        if len(sentences) < 6:
            raise ValueError("Research paragraphs must contain at least six sentences.")
        words = paragraph.split()
        if len(words) < minimum:
            paragraph += (
                " This distinction also protects the report from overstatement and keeps the "
                "interpretation aligned with the evidence actually supplied."
            )
        return ScribeResearchAgent._remove_incomplete_fragments(paragraph)

    @staticmethod
    def _remove_incomplete_fragments(text):
        clean = re.sub(r"\.{2,}", ".", str(text))
        clean = re.sub(r"\s+", " ", clean).strip()
        for punctuation in ",.;!?":
            clean = clean.replace(f" {punctuation}", punctuation)
        if clean and clean[-1] not in ".!?":
            clean += "."
        return clean

    @staticmethod
    def _complete_sentence(text, terminal="."):
        clean = re.sub(r"\.{2,}", ".", re.sub(r"\s+", " ", str(text).strip()))
        clean = clean.strip(" .")
        if terminal and clean and clean[-1] not in ".!?":
            clean += terminal
        return clean

    def _long_form_paragraph(self, topic, evidence_text, sources, conclusion):
        point_sources = self._sources_for_point(evidence_text, sources)
        citation = self._citation_for_sources(point_sources)
        paragraph = (
            f"{self._topic_sentence(evidence_text)} {citation} "
            "The directly supporting studies provide a bounded basis for this interpretation, but their findings "
            "must be read in relation to the populations, measures, settings, and analytical choices that produced them. "
            f"Moreover, the evidence suggests that {self._interpretation(evidence_text)}. {conclusion} "
            f"For {topic}, this distinction matters because it preserves the theme's analytical identity and prevents "
            "claims from being transferred to questions that the cited studies did not examine."
        )
        return self._fit_paragraph_range(paragraph, 50, 75)

    def _developed_paragraph(self, topic, evidence_text, sources, conclusion):
        point_sources = self._sources_for_point(evidence_text, sources)
        citation = self._citation_for_sources(point_sources)
        paragraph = (
            f"{self._topic_sentence(evidence_text)} {citation} "
            "The selected studies report related findings, while differences in design, setting, and emphasis caution "
            f"against treating the finding as uniformly applicable. Moreover, this evidence indicates that {self._interpretation(evidence_text)}. "
            f"{conclusion}"
        )
        if len(paragraph.split()) < 70:
            paragraph += (
                f" For {topic}, this distinction matters because a useful research argument must connect the observed "
                "pattern to its conditions, limitations, and implications rather than merely list individual findings. "
                "The resulting interpretation should guide a focused research question."
            )
        return self._fit_paragraph_range(paragraph, 50, 75)

    @staticmethod
    def _fit_paragraph_range(paragraph, minimum, maximum):
        words = paragraph.split()
        if len(words) > maximum:
            return " ".join(words[:maximum]).rstrip(" ,;:.") + "."
        return paragraph

    @staticmethod
    def _shorten(text, max_words):
        words = str(text).split()
        if len(words) <= max_words:
            return str(text).strip()
        return " ".join(words[:max_words]).rstrip(" ,;:.") + "."

    def _sources_for_point(self, point, sources):
        if not sources:
            return []
        point_tokens = self._content_tokens(point)
        scored = []
        for source in sources:
            source_text = " ".join([
                str(self._source_value(source, "title", "")),
                str(self._source_value(source, "abstract", "")),
                str(self._source_value(source, "keywords", ""))
            ])
            score = len(point_tokens.intersection(self._content_tokens(source_text)))
            scored.append((score, source))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [source for score, source in scored if score > 0][:3]
        return selected or [source for _, source in scored[:2]]

    def _cluster_sources_by_theme(self, themes, sources):
        if not themes:
            return {}
        clusters = {}
        unused = list(sources)
        for theme in themes:
            selected = self._sources_for_point(theme, sources)
            clusters[theme] = selected
            for source in selected:
                if source in unused and len(themes) > 1:
                    unused.remove(source)
        # Ensure every theme has direct evidence, while allowing a source to
        # support multiple themes only when its content genuinely overlaps.
        for index, theme in enumerate(themes):
            if not clusters[theme]:
                clusters[theme] = [sources[index % len(sources)]] if sources else []
        return clusters

    @staticmethod
    def _content_tokens(text):
        stop_words = {
            "about", "after", "again", "also", "because", "being", "between",
            "could", "from", "have", "into", "more", "most", "other", "that",
            "their", "these", "this", "those", "through", "using", "were",
            "which", "with", "within", "would"
        }
        return {
            token for token in re.findall(r"[a-zA-Z]{4,}", str(text).lower())
            if token not in stop_words
        }

    @staticmethod
    def _topic_sentence(text):
        sentence = str(text).strip()
        if not sentence:
            return "The available literature identifies a meaningful pattern in this area."
        return sentence[0].upper() + sentence[1:]

    @staticmethod
    def _interpretation(text):
        sentence = str(text).strip().rstrip(".")
        return f"this pattern should be understood in relation to {sentence.lower()}"

    @staticmethod
    def _source_value(source, key, default=""):
        if isinstance(source, dict):
            value = source.get(key, default)
        else:
            value = getattr(source, key, default)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return value if value not in (None, "") else default

    def _citation_for_sources(self, sources):
        citations = []
        normalized_sources = sorted(
            sources or [],
            key=lambda source: self._author_surname(
                self._source_value(source, "authors", "Unknown Author")
            ).lower(),
        )
        for source in normalized_sources:
            authors = self._source_value(source, "authors", "Unknown Author")
            year = self._source_value(source, "year", "n.d.")
            surname = self._author_surname(authors)
            citations.append(f"{surname}, {year}")
        return f"({'; '.join(citations)})" if citations else ""

    @staticmethod
    def _author_surname(authors):
        if isinstance(authors, list):
            author_text = str(authors[0]) if authors else "Unknown Author"
        else:
            author_text = str(authors)
        return author_text.replace(";", ",").split(",")[0].split()[-1]

    def _clean_filename(self, query: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '_', query.strip().lower())[:30]
