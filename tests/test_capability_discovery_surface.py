import json, subprocess, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class CapabilityDiscoveryTest(unittest.TestCase):
    def test_search_and_read_are_non_authorizing(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            ingress=td/"in.json"; out=td/"out.json"
            ingress.write_text(json.dumps({
              "destination":{"org":"StegVerse-002","service":"stegverse-002.capability-discovery"},
              "payload":{"operation":"SEARCH_CAPABILITIES","query":"admissibility"}
            }))
            done=subprocess.run(["python3","resident-runtime/capability_discovery_surface.py","--ingress",str(ingress),"--out",str(out)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(done.returncode,0,done.stderr)
            body=json.loads(out.read_text())
            self.assertEqual(body["authority_effect"],"NONE_DISCOVERY_ONLY")
            self.assertFalse(body["authority_transfer"])
            self.assertFalse(body["identity_constitution_prescribed"])
            self.assertTrue(any("admissibility" in json.dumps(x).lower() for x in body["result"]))

    def test_registry_has_all_nine_descriptors(self):
        snap=json.loads((ROOT/"org-boundary/registry/capability-descriptors.snapshot.json").read_text())
        self.assertEqual(len(snap["entries"]),9)
        self.assertTrue(snap["epistemic_rules"]["identity_constitution_not_prescribed"])
        repos={e["repository"] for e in snap["entries"]}
        self.assertIn("StegVerse-002/micro-node-runtime",repos)
        self.assertIn("StegVerse-002/.github",repos)

if __name__=="__main__": unittest.main()
