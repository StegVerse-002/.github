import json, tempfile, unittest
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("self_char",ROOT/"resident-runtime/self_characterization_surface.py")
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)

class SelfCharacterizationSurfaceTests(unittest.TestCase):
    def test_binding_is_org_local(self):
        b=json.loads((ROOT/"resident-runtime/self-characterization/stegverse-002.json").read_text())
        M.validate_binding(b,"StegVerse-002")
        self.assertEqual(b["execution_owner_repository"],"StegVerse-002/.github")
        self.assertEqual(b["principal"]["repository_organization"],"StegVerse-002")
        self.assertFalse(b["cross_organization_principal_execution_allowed"])

    def test_cross_org_principal_rejected(self):
        b=json.loads((ROOT/"resident-runtime/self-characterization/stegverse-002.json").read_text())
        b["principal"]["repository_organization"]="StegVerse-Labs"
        with self.assertRaises(RuntimeError):
            M.validate_binding(b,"StegVerse-002")

    def test_exact_manifest_validation(self):
        b=json.loads((ROOT/"resident-runtime/self-characterization/stegverse-002.json").read_text())
        e=b["expected_request"]
        manifest={
          "schema":"stegverse.external_organization.interaction_manifest.v1",
          "manifest_id":e["manifest_id"],"experiment_id":e["experiment_id"],
          "source_organization":{"organization_id":e["source_organization_id"]},
          "target":{"entity_id":"StegVerse-002"},"operation":e["operation"],"objective":e["objective"],
          "knowledge_policy":e["knowledge_policy"],"authority_transfer":False,
          "authority_effect_resolution":e["authority_effect_resolution"]
        }
        manifest["manifest_sha256"]=M.hashlib.sha256(M.canon(manifest)).hexdigest()
        req={"schema_version":e["schema_version"],"request_class":e["request_class"],"operation":e["operation"],"transport":e["transport"],"authority_transfer":False,"authority_effect_resolution":e["authority_effect_resolution"],"payload":{"manifest":manifest},"bindings":{"experiment_id":e["experiment_id"],"source_organization_id":e["source_organization_id"],"target_entity_id":"StegVerse-002","manifest_id":e["manifest_id"],"manifest_sha256":manifest["manifest_sha256"]}}
        self.assertEqual(M.validate_manifest(req,b)["manifest_sha256"],manifest["manifest_sha256"])
        req["payload"]["manifest"]["objective"]="changed"
        with self.assertRaises(RuntimeError): M.validate_manifest(req,b)

if __name__=="__main__": unittest.main()
