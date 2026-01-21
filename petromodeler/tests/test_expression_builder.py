from __future__ import annotations

import unittest

from petromodeler.domain.expressions import BinaryOp, Leaf, expression_from_dict
from petromodeler.domain.quantities import ElementConc
from petromodeler.ui.viewmodels.expression_chain import (
    SUPPORTED_ELEMENT_SYMBOLS,
    chain_rows_to_expression,
    default_element_for_prefix,
    expression_to_chain_rows,
    infer_carrier_from_symbol,
)


class ExpressionBuilderTest(unittest.TestCase):
    def test_expression_to_chain_rows_and_back(self) -> None:
        expr = BinaryOp(
            op="+",
            left=Leaf(ElementConc("Sr")),
            right=BinaryOp(
                op="*",
                left=Leaf(ElementConc("Nd")),
                right=Leaf(ElementConc("Eu")),
            ),
        )

        rows = expression_to_chain_rows(expr)
        rebuilt = chain_rows_to_expression(rows)

        self.assertEqual(len(rows), 3)
        self.assertEqual([row.op_to_next for row in rows], ["+", "*", "无"])
        self.assertIsInstance(rebuilt, BinaryOp)
        self.assertEqual(rebuilt.op, "*")
        self.assertIsInstance(rebuilt.left, BinaryOp)
        self.assertEqual(rebuilt.left.op, "+")

    def test_chain_rows_round_trip_via_dict(self) -> None:
        expr = BinaryOp(
            op="/",
            left=BinaryOp(
                op="-",
                left=Leaf(ElementConc("Sr")),
                right=Leaf(ElementConc("Nd")),
            ),
            right=Leaf(ElementConc("Eu")),
        )

        restored = expression_from_dict(chain_rows_to_expression(expression_to_chain_rows(expr)).to_dict())

        self.assertEqual(restored.to_dict(), chain_rows_to_expression(expression_to_chain_rows(expr)).to_dict())

    def test_supported_elements_sorted_by_atomic_mass(self) -> None:
        self.assertEqual(
            SUPPORTED_ELEMENT_SYMBOLS,
            ["B", "Sc", "Ti", "V", "Cr", "Mn", "Ni", "Co", "Cu", "Zn", "Sr", "Y", "Zr", "Nb", "Ba", "Hf", "Ta"],
        )

    def test_default_element_by_axis_prefix(self) -> None:
        self.assertEqual(default_element_for_prefix("xexpr"), "B")
        self.assertEqual(default_element_for_prefix("yexpr"), "Sr")

    def test_infer_carrier_from_isotope_symbol(self) -> None:
        self.assertEqual(infer_carrier_from_symbol("δ11B"), "B")
        self.assertEqual(infer_carrier_from_symbol("87Sr/86Sr"), "Sr")
        self.assertEqual(infer_carrier_from_symbol("εNd"), "Nd")
        self.assertIsNone(infer_carrier_from_symbol(""))


if __name__ == "__main__":
    unittest.main()
