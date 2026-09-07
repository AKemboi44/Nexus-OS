import os
import re
import time
import pandas as pd
from .base_agent import BaseAgent


class SquireAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='Squire', role='Documentation & Export')

    def execute(self, dossier, **kwargs):
        print(f"[Squire | Documentation & Export]: Generating enhanced audit trail...")

        # 1. Extract base properties safely
        query = getattr(dossier, 'query', 'Unknown Query')
        included_sources = getattr(dossier, 'included_sources', [])

        # Extract Phase 5 properties with fallbacks
        themes = getattr(dossier, 'themes', [])
        contradictions = getattr(dossier, 'contradictions', [])
        gaps = getattr(dossier, 'research_gaps', getattr(dossier, 'identified_gaps', []))
        opportunities = getattr(dossier, 'opportunity_areas', [])

        # =========================================================================
        # DYNAMIC FILENAME LOGIC: Run-scopes file output names based on topic + time
        # =========================================================================
        # Convert spaces/symbols to underscores and remove messy characters
        clean_topic = re.sub(r'[^a-zA-Z0-9]', '_', query.lower().strip())
        clean_topic = re.sub(r'_+', '_', clean_topic)  # Collapse duplicate underscores
        timestamp_suffix = time.strftime("%Y%m%d_%H%M%S")

        # Keep the topic segment concise (max 30 characters) to prevent Windows path layout issues
        export_path = f"research_audit_{clean_topic[:30]}_{timestamp_suffix}.xlsx"
        # =========================================================================

        # 2. Build the structural Executive Summary dataframe
        df_summary = pd.DataFrame({
            "Research Query": [query],
            "Total Ingested Sources": [len(included_sources)],
            "Timestamp": [time.strftime("%Y-%m-%d %H:%M:%S")]
        })

        # =========================================================================
        # INGESTED SOURCES UNPACKING LOGIC: Loop through all collected assets
        # =========================================================================
        sources_records = []
        for index, src in enumerate(included_sources, 1):
            src_id = getattr(src, 'id', dict(src).get('id', 'N/A') if isinstance(src, dict) else 'N/A')
            title = getattr(src, 'title',
                            dict(src).get('title', 'Unknown Title') if isinstance(src, dict) else 'Unknown Title')
            year = getattr(src, 'year', dict(src).get('year', 'N/A') if isinstance(src, dict) else 'N/A')
            url = getattr(src, 'url', dict(src).get('url', 'N/A') if isinstance(src, dict) else 'N/A')

            authors_raw = getattr(src, 'authors', dict(src).get('authors', []) if isinstance(src, dict) else [])
            authors_str = ", ".join(authors_raw) if isinstance(authors_raw, list) else str(authors_raw)

            sources_records.append({
                "Index": index,
                "Source ID": src_id,
                "Document Title": title,
                "Authors": authors_str,
                "Publication Year": year,
                "Resource URL": url
            })

        if not sources_records:
            sources_records.append({
                "Index": "-", "Source ID": "N/A", "Document Title": "No papers available",
                "Authors": "N/A", "Publication Year": "N/A", "Resource URL": "N/A"
            })

        df_sources_audit = pd.DataFrame(sources_records)
        # =========================================================================

        # Build structural dataframes for Phase 5 matrices
        df_themes = pd.DataFrame({"Key Themes Discovered": themes if themes else ["No themes generated."]})
        df_contradictions = pd.DataFrame({"Identified Contradictions": contradictions if contradictions else [
            "No contradictions found or analyzed."]})
        df_gaps = pd.DataFrame({"Structural Research Gaps": gaps if gaps else ["No tracked research gaps discovered."]})
        df_opportunities = pd.DataFrame(
            {"Opportunity Areas": opportunities if opportunities else ["No strategic opportunity areas mapped."]})

        # 3. Encapsulate workbook saving logic
        def write_excel_safely(path):
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df_summary.to_excel(writer, sheet_name='Executive Summary', index=False)
                df_sources_audit.to_excel(writer, sheet_name='Ingested Sources Audit', index=False)
                df_themes.to_excel(writer, sheet_name='Key Themes', index=False)
                df_contradictions.to_excel(writer, sheet_name='Contradictions', index=False)
                df_gaps.to_excel(writer, sheet_name='Research Gaps', index=False)
                df_opportunities.to_excel(writer, sheet_name='Strategic Opportunities', index=False)

        try:
            write_excel_safely(export_path)
            print(f"[Squire Success]: Report generated cleanly at {export_path}")
        except PermissionError:
            # Emergency bypass fallback if the file happens to be locked open by another app
            fallback_timestamp = int(time.time())
            export_path = f'research_audit_emergency_{fallback_timestamp}.xlsx'
            print(f"[Squire Warning]: Primary file path locked. Saving emergency backup copy to {export_path}")
            write_excel_safely(export_path)
        except Exception as e:
            print(f"[Squire Error]: Critical exception while building data log: {e}")

        return export_path
