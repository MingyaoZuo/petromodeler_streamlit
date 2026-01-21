from __future__ import annotations

import unittest
from io import BytesIO

import pandas as pd

from petromodeler.application.services.export_service import ExportService


class ExportServiceTest(unittest.TestCase):
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
