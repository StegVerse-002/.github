from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("sv002_pre_t0",ROOT/"resident-runtime/evaluate_sv002_pre_t0_readiness.py")
mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)

class TestSV002PreT0Readiness(unittest.TestCase):
    def test_clean_principal_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.assertTrue(mod.require_clean_principal_state(root)["pass"])
            (root/"S0.json").write_text("{}")
            value=mod.require_clean_principal_state(root)
            self.assertFalse(value["pass"])
            self.assertIn("S0.json",value["occupancy_blockers"])

    def test_resident_node_requires_explicit_eligibility(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"node.json"
            p.write_text(json.dumps({
                "schema":"stegverse.resident-node-eligibility/v1",
                "node_id":"node-1",
                "declared":True,
                "eligible":True,
                "owned_or_federated_by_stegverse":True,
                "authority_effect":"NONE",
            }))
            self.assertTrue(mod.verify_node_evidence(p)["pass"])
            value=json.loads(p.read_text());value["eligible"]=False;p.write_text(json.dumps(value))
            self.assertFalse(mod.verify_node_evidence(p)["pass"])

    def test_receipt_schema_is_non_authorizing(self):
        schema=json.loads((ROOT/"schemas/sv002-pre-t0-readiness.schema.json").read_text())
        self.assertEqual(schema["properties"]["authority_effect"]["const"],"NONE")
        self.assertEqual(schema["properties"]["principal_executed"]["const"],False)
        self.assertIn("READY_FOR_T0",schema["properties"]["readiness_state"]["enum"])

if __name__=="__main__": unittest.main()
