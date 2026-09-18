import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "invoke_sv002_experiment_rerun",
    ROOT / "resident-runtime" / "invoke_sv002_experiment_rerun.py",
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class SV002ExperimentRerunCallableBindingTests(unittest.TestCase):
    def test_builds_exact_frozen_request(self):
        request, manifest = M.build_frozen_request()
        self.assertEqual(request["operation"], "REQUEST_SELF_CHARACTERIZATION")
        self.assertEqual(request["transport"], "InTr")
        self.assertEqual(manifest["experiment_id"], "STEGVERSE-002-SELF-CHARACTERIZATION-001")
        self.assertEqual(manifest["target"]["entity_id"], "StegVerse-002")
        self.assertEqual(
            request["bindings"]["manifest_sha256"],
            manifest["manifest_sha256"],
        )

    def test_exactly_once_same_host_publication(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            mesh = Path(td) / "mesh"
            env = {
                "STEGVERSE_SELF_CHAR_STATE_ROOT": str(state),
                "STEGVERSE_ORG_FEDERATION_ROOT": str(mesh),
                "STEGVERSE_ORG_FEDERATION_GATEWAY_URL": "",
                "GITHUB_ACTIONS": "",
                "CI": "",
            }
            with patch.dict(os.environ, env, clear=False):
                first = M.invoke_once()
                second = M.invoke_once()

            self.assertEqual(first["state"], "SUBMITTED_EXISTING_FEDERATION_EDGE")
            self.assertEqual(second["state"], "ALREADY_SUBMITTED_NO_SECOND_REQUEST")
            self.assertEqual(first["frame_sha256"], second["frame_sha256"])
            self.assertEqual(len(list((mesh / "frames.d").glob("*.json"))), 1)
            bound = json.loads((state / "RERUN_REQUEST_BOUND.json").read_text())
            self.assertEqual(bound["state"], "REQUEST_BOUND")
            self.assertEqual(bound["invocation_count"], 1)

    def test_hosted_execution_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            env = {
                "STEGVERSE_SELF_CHAR_STATE_ROOT": str(Path(td) / "state"),
                "STEGVERSE_ORG_FEDERATION_ROOT": str(Path(td) / "mesh"),
                "GITHUB_ACTIONS": "true",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(RuntimeError, "hosted execution prohibited"):
                    M.invoke_once()


if __name__ == "__main__":
    unittest.main()
