import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("boundary",ROOT/"org-boundary/runtime/process_boundary.py")
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)

class SelfCharacterizationBoundaryReceiptTests(unittest.TestCase):
    def test_receipts_preserve_live_time_and_disposition(self):
        base={"packet_id":"pkt","service_id":"stegverse-002.self-characterization","payload_hash":"a"*64}
        r1=M.make_receipt("INGRESS_ACCEPTED",base,None)
        r2=M.make_receipt("DISPATCHED",base,r1["receipt_id"])
        r3=M.make_receipt("CONSUMED",base,r2["receipt_id"],disposition="ATTEMPT_RECORDED")
        self.assertTrue(r1["observed_at"])
        self.assertEqual(r2["previous_receipt_id"],r1["receipt_id"])
        self.assertEqual(r3["previous_receipt_id"],r2["receipt_id"])
        self.assertEqual(r3["application_disposition"],"ATTEMPT_RECORDED")
        self.assertNotIn("application_disposition",r1)

    def test_boundary_receipt_ids_are_stable_over_timestamp(self):
        base={"packet_id":"pkt","service_id":"stegverse-002.self-characterization","payload_hash":"a"*64}
        r1=M.make_receipt("INGRESS_ACCEPTED",base,None)
        r2=M.make_receipt("INGRESS_ACCEPTED",base,None)
        self.assertEqual(r1["receipt_id"],r2["receipt_id"])
        self.assertEqual(r1["evidence_hash"],r2["evidence_hash"])

if __name__=="__main__":
    unittest.main()
