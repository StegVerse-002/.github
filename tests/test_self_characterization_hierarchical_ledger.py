import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("process_boundary",ROOT/"org-boundary"/"runtime"/"process_boundary.py")
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


class HierarchicalLedgerTests(unittest.TestCase):
    def test_org_root_includes_exact_repo_root_and_boundary_order(self):
        with tempfile.TemporaryDirectory() as td:
            state_root=Path(td)
            repo_body={
                "schema_version":"stegverse.hierarchical-ledger-root/v1",
                "scope_type":"repository",
                "scope_id":"StegVerse-002/micro-node-runtime",
                "root_id":"REPO-TEST",
                "generated_at":"2026-09-01T00:00:00+00:00",
                "run_id":"SV002-RUN-TEST",
                "previous_root_hash":None,
                "range":{"first_receipt_id":"TR-1","last_receipt_id":"TR-2","receipt_count":2,"ordered_root_hash":"a"*64},
                "children":[],
                "reconstruction":{"status":"NOT_ATTEMPTED","descendant_resolution_required":False,"reference":"TRANSITION_RECEIPTS.json"},
            }
            repo_root={**repo_body,"root_hash":M.digest(repo_body)}
            (state_root/"REPOSITORY_LEDGER_ROOT.json").write_text(json.dumps(repo_root))
            (state_root/"S0.json").write_text(json.dumps({"run_id":"SV002-RUN-TEST"}))
            receipts=[]
            prev=None
            base={"packet_id":"pkt","service_id":"stegverse-002.self-characterization","payload_hash":"b"*64}
            for kind in M.KINDS:
                row=M.make_receipt(kind,base,prev,hb_epoch=4096,disposition="COMPLETED" if kind in {"CONSUMED","RESULT_BOUND","EGRESS_EMITTED"} else None)
                receipts.append(row); prev=row["receipt_id"]
            bundle={"receipts":receipts}
            root=M.build_org_ledger_root(state_root,bundle)
            self.assertEqual(root["scope_type"],"organization")
            self.assertEqual(root["children"][0]["root_hash"],repo_root["root_hash"])
            self.assertEqual(root["range"]["first_receipt_id"],receipts[0]["receipt_id"])
            self.assertEqual(root["range"]["last_receipt_id"],receipts[-1]["receipt_id"])
            self.assertEqual(root["generated_at"],"hb-epoch:4096")
            body=dict(root); claimed=body.pop("root_hash")
            self.assertEqual(claimed,M.digest(body))


if __name__=="__main__":
    unittest.main()
