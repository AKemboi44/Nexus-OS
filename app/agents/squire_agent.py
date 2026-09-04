import os
import pandas as pd
from .base_agent import BaseAgent

class SquireAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='Squire', role='Documentation & Export')

    def execute(self, dossier, export_path: str = 'research_audit_v100.xlsx') -> str:
        self.announce(f'Generating enhanced audit trail at {export_path}...')

        # Prepare DataFrames from Dossier
        df_included = pd.DataFrame(dossier.included_sources)
        df_excluded = pd.DataFrame(dossier.excluded_sources)

        # Fallback for empty data
        if df_included.empty:
            df_included = pd.DataFrame(columns=['Title', 'Abstract', 'Year'])
        if df_excluded.empty:
            df_excluded = pd.DataFrame(columns=['Title', 'Reason', 'Year'])

        with pd.ExcelWriter(export_path) as writer:
            df_included.to_excel(writer, sheet_name='Included Sources', index=False)
            df_excluded.to_excel(writer, sheet_name='Excluded Sources', index=False)

        return export_path