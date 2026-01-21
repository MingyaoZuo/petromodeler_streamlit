"""Dataset import service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd


class ImportService:
    def load_excel(self, file_obj) -> pd.DataFrame:
        """Load an Excel file from a path or a file-like object."""
        df = pd.read_excel(file_obj)
        df.columns = [str(c) for c in df.columns]
        return df

    def infer_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        cols = []
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                cols.append(str(c))
        return cols
