"""Export service (details tables / plot).

For Streamlit, the most useful export is an in-memory Excel bytes payload for
st.download_button.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import pandas as pd


class ExportService:
    _PLOT_FORMATS = {"png", "jpeg", "svg", "pdf"}
    _PLOT_FORMATS_BY_SUFFIX = {
        ".png": "png",
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".svg": "svg",
        ".pdf": "pdf",
    }

    def dataframe_to_excel_bytes(self, df: pd.DataFrame, sheet_name: str = "details") -> bytes:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return buf.getvalue()

    def figure_to_image_bytes(self, figure, image_format: str, dpi: int = 300) -> bytes:
        """Render a Matplotlib figure for Streamlit's download button."""
        normalized_format = image_format.lower().strip()
        if normalized_format == "jpg":
            normalized_format = "jpeg"
        if normalized_format not in self._PLOT_FORMATS:
            raise ValueError(f"Unsupported plot format: {image_format}")

        buf = BytesIO()
        # Matplotlib's default SVG output converts glyphs into paths.  Keeping
        # the font type as "none" produces <text> elements that CorelDRAW and
        # other vector editors can select and edit as text.
        svg_settings = {"svg.fonttype": "none"} if normalized_format == "svg" else {}
        with mpl.rc_context(svg_settings):
            figure.savefig(
                buf,
                format=normalized_format,
                dpi=dpi,
                bbox_inches="tight",
            )
        return buf.getvalue()

    def figure_to_file(self, figure, path: str | Path, dpi: int = 300) -> Path:
        """Save a figure to a path whose extension selects its output format."""
        target = Path(path).expanduser()
        try:
            image_format = self._PLOT_FORMATS_BY_SUFFIX[target.suffix.lower()]
        except KeyError as exc:
            supported = ", ".join(sorted(self._PLOT_FORMATS_BY_SUFFIX))
            raise ValueError(f"Unsupported plot filename extension: {target.suffix} ({supported})") from exc

        target.write_bytes(self.figure_to_image_bytes(figure, image_format, dpi=dpi))
        return target

    @staticmethod
    def bytes_to_file(data: bytes, path: str | Path) -> Path:
        """Write an already-exported payload to a user-selected local path."""
        target = Path(path).expanduser()
        target.write_bytes(data)
        return target

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
