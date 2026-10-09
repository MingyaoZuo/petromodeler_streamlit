from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import matplotlib.pyplot as plt

from petromodeler.application.services.export_service import ExportService


class ExportServiceTest(unittest.TestCase):
    def test_figure_exports_to_requested_image_formats(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        service = ExportService()
        try:
            jpeg = service.figure_to_image_bytes(fig, "jpeg")
            svg = service.figure_to_image_bytes(fig, "svg")
        finally:
            plt.close(fig)

        self.assertTrue(jpeg.startswith(b"\xff\xd8\xff"))
        self.assertIn(b"<svg", svg)

    def test_figure_export_rejects_unknown_format(self) -> None:
        fig, _ = plt.subplots()
        try:
            with self.assertRaises(ValueError):
                ExportService().figure_to_image_bytes(fig, "gif")
        finally:
            plt.close(fig)

    def test_figure_saves_using_filename_extension(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        try:
            with TemporaryDirectory() as temp_dir:
                target = ExportService().figure_to_file(fig, Path(temp_dir) / "model.svg")
                self.assertEqual(target.suffix, ".svg")
                self.assertIn(b"<svg", target.read_bytes())
        finally:
            plt.close(fig)

    def test_exported_bytes_can_be_saved_to_selected_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            target = ExportService().bytes_to_file(b"xlsx-payload", Path(temp_dir) / "result.xlsx")
            self.assertEqual(target.read_bytes(), b"xlsx-payload")

    def test_grouped_dataframes_are_exported_to_one_sheet(self) -> None:
        service = ExportService()
        excel_bytes = service.grouped_dataframes_to_single_sheet_excel_bytes(
            [
                ("Group1", "FC", pd.DataFrame({"F": [1.0, 0.5], "Sr": [10.0, 20.0]})),
                ("Group2", "AFC", pd.DataFrame({"F": [1.0], "Nd": [3.0]})),
            ]
        )

        workbook = pd.ExcelFile(BytesIO(excel_bytes))
        exported = pd.read_excel(workbook, sheet_name="details")

        self.assertEqual(workbook.sheet_names, ["details"])
        self.assertEqual(exported["参数组"].tolist(), ["Group1", "Group1", "Group2"])
        self.assertEqual(exported["模型简称"].tolist(), ["FC", "FC", "AFC"])
        self.assertEqual(exported["F"].tolist(), [1.0, 0.5, 1.0])
        self.assertEqual(exported["Sr"].dropna().tolist(), [10.0, 20.0])
        self.assertEqual(exported["Nd"].dropna().tolist(), [3.0])


if __name__ == "__main__":
    unittest.main()
