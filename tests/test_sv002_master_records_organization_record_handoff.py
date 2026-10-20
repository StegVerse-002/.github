#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
#: The supplied epoch process_boundary hands the publisher; it never reads a clock.
HB_EPOCH="4096"
SCRIPT=ROOT/"resident-runtime/submit_sv002_self_characterization_to_master_records.py"
REQUIRED=(
    "S0.json","EXPERIMENT_EXECUTION_RECEIPT.json","SELF_CHARACTERIZATION.md",
    "SELF_CHARACTERIZATION_FORMAL.json","INTERACTION_RECEIPT_CHAIN.json",
    "TRANSITION_EFFECTS.json","TRANSITION_RECEIPTS.json","TRANSITION_RECEIPTS.live.jsonl",
    "ORG_BOUNDARY_RECEIPTS.json","ORG_BOUNDARY_RECEIPTS.live.jsonl",
    "REPOSITORY_LEDGER_ROOT.json","ORGANIZATION_LEDGER_ROOT.json",
)

class TestSV002MasterRecordsOrganizationRecordHandoff(unittest.TestCase):
    def _materialize(self,state:Path)->str:
        run_id="SV002-RUN-"+"a"*32
        for name in REQUIRED:
            p=state/name
            if name=="S0.json":
                value={"experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001","run_id":run_id}
                p.write_text(json.dumps(value),encoding="utf-8")
            elif name=="EXPERIMENT_EXECUTION_RECEIPT.json":
                value={"schema":"stegverse.self-characterization-execution-receipt/v0.3","experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001","run_id":run_id,"state":"COMPLETED","principal_run_completed":True}
                p.write_text(json.dumps(value),encoding="utf-8")
            elif name=="ORGANIZATION_LEDGER_ROOT.json":
                p.write_text(json.dumps({"root_hash":"b"*64}),encoding="utf-8")
            elif name.endswith(".jsonl"):
                p.write_text("{}\n",encoding="utf-8")
            else:
                p.write_text("{}\n" if name.endswith(".json") else "result\n",encoding="utf-8")
        return run_id

    def test_legacy_handoff_receipt_prevents_republish(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state=root/"state"; state.mkdir(); mesh=root/"mesh"
            self._materialize(state)
            env=dict(os.environ);env["STEGVERSE_ORG_FEDERATION_ROOT"]=str(mesh)
            first=subprocess.run(["python3",str(SCRIPT),"--state-root",str(state),"--hb-epoch",HB_EPOCH],cwd=ROOT,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(first.returncode,0,first.stderr)
            new=state/"MASTER_RECORDS_ORGANIZATION_RECORD_HANDOFF.json"
            legacy=state/"MASTER_RECORDS_CUSTODY_HANDOFF.json"
            new.rename(legacy)
            second=subprocess.run(["python3",str(SCRIPT),"--state-root",str(state),"--hb-epoch",HB_EPOCH],cwd=ROOT,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertEqual(json.loads(second.stdout)["state"],"ALREADY_PUBLISHED_NO_REPUBLISH")
            self.assertFalse(new.exists())
            self.assertEqual(len(list((mesh/"frames.d").glob("*.json"))),1)

    def test_publishes_once_without_rerunning_principal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state=root/"state"; state.mkdir(); mesh=root/"mesh"
            run_id="SV002-RUN-"+"a"*32
            for name in REQUIRED:
                p=state/name
                if name=="S0.json":
                    value={"experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001","run_id":run_id}
                    p.write_text(json.dumps(value),encoding="utf-8")
                elif name=="EXPERIMENT_EXECUTION_RECEIPT.json":
                    value={"schema":"stegverse.self-characterization-execution-receipt/v0.3","experiment_id":"STEGVERSE-002-SELF-CHARACTERIZATION-001","run_id":run_id,"state":"COMPLETED","principal_run_completed":True}
                    p.write_text(json.dumps(value),encoding="utf-8")
                elif name=="ORGANIZATION_LEDGER_ROOT.json":
                    p.write_text(json.dumps({"root_hash":"b"*64}),encoding="utf-8")
                elif name.endswith(".jsonl"):
                    p.write_text("{}\n",encoding="utf-8")
                else:
                    p.write_text("{}\n" if name.endswith(".json") else "result\n",encoding="utf-8")
            env=dict(os.environ);env["STEGVERSE_ORG_FEDERATION_ROOT"]=str(mesh)
            first=subprocess.run(["python3",str(SCRIPT),"--state-root",str(state),"--hb-epoch",HB_EPOCH],cwd=ROOT,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(first.returncode,0,first.stderr)
            receipt=json.loads((state/"MASTER_RECORDS_ORGANIZATION_RECORD_HANDOFF.json").read_text())
            self.assertFalse((state/"MASTER_RECORDS_CUSTODY_HANDOFF.json").exists())
            self.assertEqual(receipt["state"],"PUBLISHED_FOR_MASTER_RECORDS_ORGANIZATION_RECORD")
            self.assertEqual(receipt["schema"],"stegverse.sv002-master-records-organization-record-handoff/v1")
            self.assertFalse(receipt["principal_rerun_required"])
            frames=list((mesh/"frames.d").glob("*.json"))
            self.assertEqual(len(frames),1)
            reference=json.loads(frames[0].read_text())["heartbeat_reference"]
            self.assertEqual(reference["epoch"],int(HB_EPOCH))
            self.assertIs(reference["derived_from_clock"],False)
            self.assertNotIn("sampled_unix_ns",reference)
            self.assertEqual(receipt["observed_at"],"hb-epoch:"+HB_EPOCH)
            second=subprocess.run(["python3",str(SCRIPT),"--state-root",str(state),"--hb-epoch",HB_EPOCH],cwd=ROOT,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertEqual(json.loads(second.stdout)["state"],"ALREADY_PUBLISHED_NO_REPUBLISH")
            self.assertEqual(len(list((mesh/"frames.d").glob("*.json"))),1)

    def test_an_absent_epoch_is_refused_six_field_and_nothing_is_published(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state=root/"state"; state.mkdir(); mesh=root/"mesh"
            self._materialize(state)
            env={k:v for k,v in os.environ.items() if k!="STEGVERSE_HB_EPOCH"};env["STEGVERSE_ORG_FEDERATION_ROOT"]=str(mesh)
            refused=subprocess.run(["python3",str(SCRIPT),"--state-root",str(state)],cwd=ROOT,env=env,capture_output=True,text=True,check=False)
            self.assertEqual(refused.returncode,1,refused.stderr)
            self.assertNotIn("Traceback",refused.stderr)
            refusal=json.loads(refused.stdout)
            self.assertEqual(refusal["failure_code"],"HB_EPOCH_NOT_SUPPLIED")
            for field in ("failed_predicate","required_evidence_or_repair","retry_entrypoint","owning_existing_goal","next_attempt"):
                self.assertTrue(refusal[field],field)
            self.assertFalse(mesh.exists())
            self.assertFalse((state/"MASTER_RECORDS_ORGANIZATION_RECORD_HANDOFF.json").exists())

if __name__=="__main__": unittest.main()
