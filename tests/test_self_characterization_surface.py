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

if __name__=="__main__": unittest.main()
