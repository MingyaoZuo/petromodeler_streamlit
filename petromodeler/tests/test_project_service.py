from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from petromodeler.application.services.project_service import ProjectService
from petromodeler.application.state.app_state import AppState
from petromodeler.application.state.group_state import GroupState


class ProjectServiceTest(unittest.TestCase):
    def test_project_json_round_trip(self) -> None:
        service = ProjectService()
        state = AppState()
        state.groups.append(GroupState(group_id="G1", name="Group1", model_id="fc", params={"k": 1.0}))

        restored = service.loads(service.dumps(state))

        self.assertEqual(restored.groups[0].group_id, "G1")
        self.assertEqual(restored.groups[0].params, {"k": 1.0})

    def test_payload_digest_is_stable(self) -> None:
        service = ProjectService()

        self.assertEqual(service.payload_digest(b"abc"), service.payload_digest(b"abc"))
        self.assertNotEqual(service.payload_digest(b"abc"), service.payload_digest(b"abcd"))

    def test_save_text_resolves_json_path(self) -> None:
        service = ProjectService()

        with tempfile.TemporaryDirectory() as tmp:
            saved_path = service.save_text("{}", Path(tmp) / "project")

            self.assertEqual(saved_path.name, "project.json")
            self.assertEqual(saved_path.read_text(encoding="utf-8"), "{}")


if __name__ == "__main__":
    unittest.main()
