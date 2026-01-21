"""Export service (details tables / plot).

For Streamlit, the most useful export is an in-memory Excel bytes payload for
st.download_button.
"""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import pandas as pd


class ExportService:
    def dataframe_to_excel_bytes(self, df: pd.DataFrame, sheet_name: str = "details") -> bytes:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return buf.getvalue()
