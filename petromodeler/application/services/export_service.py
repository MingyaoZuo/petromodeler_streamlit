"""Export service (details tables / plot).

For Streamlit, the most useful export is an in-memory Excel bytes payload for
st.download_button.
"""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd


class ExportService:
    def dataframe_to_excel_bytes(self, df: pd.DataFrame, sheet_name: str = "details") -> bytes:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return buf.getvalue()

    def grouped_dataframes_to_single_sheet_excel_bytes(
        self,
        grouped_tables: Iterable[tuple[str, str, pd.DataFrame]],
        sheet_name: str = "details",
    ) -> bytes:
        frames: list[pd.DataFrame] = []
        for group_name, model_short_name, df in grouped_tables:
            table = df.copy()
            table.insert(0, self._unique_column_name(table, "模型简称"), model_short_name)
            table.insert(0, self._unique_column_name(table, "参数组"), group_name)
            frames.append(table)

        combined = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
        return self.dataframe_to_excel_bytes(combined, sheet_name=sheet_name)

    @staticmethod
    def _unique_column_name(df: pd.DataFrame, base_name: str) -> str:
        name = base_name
        index = 2
        while name in df.columns:
            name = f"{base_name}_{index}"
            index += 1
        return name
