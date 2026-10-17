"""Emission defaults to the published organization ledger ref.

The appends in this file use a temporary git repository and a test ref. They
are not authentic production receipts, and they do not write
``refs/stegverse/organization-ledger`` in this checkout. Authority and time
are constraint variables. A disposition is transition evidence only.
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REF = "refs/test/organization-ledger"
NAMESPACE = "repository-ledger/StegVerse-002/.github"
PUBLISHED_REF = "refs/stegverse/organization-ledger"
COMMUNICATION_ID = "diagnostic-self-closure-test-001"


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger_store = _load("published_ledger_store", "resident-runtime/ledger_store.py")
organization = _load("published_org_append", "resident-runtime/aggregate_repo_transition.py")
repository = _load("published_repo_emit", ".stegverse/transition-ledger/emit.py")
readback = _load("published_readback", "resident-runtime/organization_ledger_readback.py")
ingress = _load("published_ingress", "resident-runtime/intr_destination_ingress.py")


def _published_ref_absent():
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", PUBLISHED_REF],
        capture_output=True)
    return completed.returncode != 0


class PublishedRefBindingTests(unittest.TestCase):
    def test_the_contract_binds_both_chains_to_the_published_ref(self):
        contract = json.loads((ROOT / ".stegverse/transition-ledger/contract.json").read_text())
        org_contract = json.loads((ROOT / ".stegverse/transition-ledger/org-contract.json").read_text())
        location = contract["repository_ledger_location"]
        self.assertEqual(org_contract["organization"], "StegVerse-002")
        self.assertEqual(org_contract["organization_ledger_repository"], "StegVerse-002/.github")
        self.assertEqual(org_contract["organization_ledger_ref"], PUBLISHED_REF)
        self.assertEqual(location["repository"], org_contract["organization_ledger_repository"])
        self.assertEqual(location["ref"], PUBLISHED_REF)
        self.assertIs(location["new_ledger_root"], False)
        self.assertEqual(location["namespace"], "repository-ledger/" + contract["repository"])
        self.assertEqual(contract["replay_rule"],
                         "REPOSITORY_REPLAY_MUST_NOT_REQUIRE_ORGANIZATION_OR_ECOSYSTEM_REPLAY")

    def test_an_unset_root_names_the_published_ref_and_writes_nothing(self):
        self.assertTrue(_published_ref_absent())
        env = {key: value for key, value in os.environ.items()
               if key not in ("STEGVERSE_REPO_LEDGER_ROOT", "STEGVERSE_ORG_LEDGER_ROOT", "XDG_STATE_HOME")}
        with mock.patch.dict(os.environ, env, clear=True):
            repo_root = repository.lr()
            org_root = organization.ledger_root()
        self.assertEqual(repo_root.ref, PUBLISHED_REF)
        self.assertEqual(repo_root.namespace, NAMESPACE)
        self.assertEqual(org_root.ref, PUBLISHED_REF)
        self.assertIsNone(org_root.namespace)
        self.assertEqual(repo_root.repository, ROOT)
        self.assertTrue(_published_ref_absent())

    def test_the_workflow_appends_pushes_the_published_ref_and_reads_it_back(self):
        workflow = (ROOT / ".github/workflows/organization-ledger-transition.yml").read_text()
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("--self-closure", workflow)
        self.assertIn('export STEGVERSE_ORG_LEDGER_ROOT="git+$GITHUB_WORKSPACE#$LEDGER_REF"', workflow)
        self.assertIn(
            'export STEGVERSE_REPO_LEDGER_ROOT="git+$GITHUB_WORKSPACE#$LEDGER_REF:$REPO_LEDGER_NAMESPACE"',
            workflow)
        self.assertIn('git push origin "$LEDGER_REF:$LEDGER_REF"', workflow)
        self.assertEqual(workflow.count("git push origin"), 1)
        self.assertIn("--repository-namespace", workflow)
        self.assertIn("--closure-result", workflow)
        self.assertIn("communication_id", workflow)
        self.assertNotIn("refs/stegverse/repository-ledger", workflow)
        self.assertNotIn("runner.temp }}/repo-ledger", workflow)
        self.assertNotIn("grant", workflow.lower())
        self.assertNotIn("capability_destination_bindings", workflow)

    def test_federation_and_the_boundary_copy_are_not_this_change(self):
        federation = (ROOT / "org-boundary/registry/federation.json").read_text(encoding="utf-8")
        self.assertNotIn("intr-destination", federation)
        boundary = json.loads((ROOT / "org-runtime/interlock-intr.json").read_text(encoding="utf-8"))
        self.assertNotIn("capability_destination_bindings", boundary["egress"])


class _TemporaryRef(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.repo = Path(self._dir.name) / "ledger.git"
        self.organization_location = "git+" + str(self.repo) + "#" + REF
        self.repository_location = self.organization_location + ":" + NAMESPACE
        self.env = {
            "STEGVERSE_ORG_LEDGER_ROOT": self.organization_location,
            "STEGVERSE_REPO_LEDGER_ROOT": self.repository_location,
        }
        previous = {name: os.environ.get(name) for name in self.env}
        os.environ.update(self.env)

        def restore():
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.addCleanup(restore)


class SharedRefTests(_TemporaryRef):
    def test_both_ledgers_share_one_ref_and_a_later_append_extends_the_chain(self):
        with mock.patch.dict(os.environ, self.env):
            first = repository.append("shared-1", "TEST", "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                      {"n": 1}, "NONE", hb_epoch=32)
            consumed = organization.append(first, "REPO_STATE_PROPAGATION",
                                           "sha256:" + "c" * 64, "sha256:" + "d" * 64,
                                           {"communication_id": COMMUNICATION_ID}, "NONE", hb_epoch=32)
            second = repository.append("shared-2", "TEST", "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                       {"n": 2}, "NONE", hb_epoch=33)
            organization.append(second, "REPO_STATE_PROPAGATION",
                                "sha256:" + "c" * 64, "sha256:" + "e" * 64,
                                {"communication_id": COMMUNICATION_ID}, "NONE", hb_epoch=33)
        self.assertIsNone(first["previous_receipt_sha256"])
        self.assertEqual(second["previous_receipt_sha256"], first["receipt_sha256"])
        self.assertEqual(consumed["repo_receipt_sha256"], first["receipt_sha256"])
        self.assertEqual(consumed["source_transition_sha256"], first["receipt_sha256"])
        organization_result = readback.readback(self.organization_location)
        repository_result = readback.repository_readback(self.organization_location, NAMESPACE)
        self.assertEqual(organization_result["chain_length"], 2)
        self.assertEqual(repository_result["chain_length"], 2)
        self.assertFalse(repository_result["replay_read_organization_receipts"])
        self.assertTrue(repository_result["every_receipt_retained_in_organization_ledger"])
        self.assertNotEqual(REF, PUBLISHED_REF)
        self.assertTrue(_published_ref_absent())


class DiagnosticSelfClosureTests(_TemporaryRef):
    def test_a_self_closure_appends_repo_and_org_receipts_with_communication_id(self):
        mesh = Path(self._dir.name) / "mesh"
        with mock.patch.dict(os.environ, self.env):
            closed = ingress.diagnostic_self_closure(COMMUNICATION_ID, mesh_root=mesh, hb_epoch=32)
        self.assertEqual(closed["disposition"], "ALLOW", closed.get("closure_findings") or closed.get("detail"))
        self.assertIs(closed["closed"], True)
        self.assertEqual(closed["communication_id"], COMMUNICATION_ID)
        self.assertIs(closed["peer_serves_this_capability_is_proven_here"], False)
        for field in ("routing_authority_constraint", "admission_authority_constraint",
                      "execution_authority_constraint", "time_constraint"):
            self.assertEqual(closed[field], "CONSTRAINT_VARIABLE", field)
        self.assertEqual(closed["disposition_role"], "TRANSITION_EVIDENCE_ONLY")
        organization_result = readback.readback(self.organization_location)
        repository_result = readback.repository_readback(self.organization_location, NAMESPACE)
        bound = readback.bind_closure(organization_result, repository_result, closed)
        self.assertEqual(bound["pairs_bound"], 3)
        self.assertTrue(bound["closure_receipts_carry_communication_id"])
        self.assertEqual(organization_result["chain_length"], 3)
        self.assertEqual(repository_result["chain_length"], 3)
        # A second run of the same diagnostic is answered from the chain, even
        # when its frame is stamped at another epoch. The mesh is only this
        # run's queue, so the retry gets its own.
        with mock.patch.dict(os.environ, self.env):
            again = ingress.diagnostic_self_closure(
                COMMUNICATION_ID, mesh_root=Path(self._dir.name) / "mesh-retry", hb_epoch=40)
        self.assertEqual(again["closure_repository_receipt_sha256"],
                         closed["closure_repository_receipt_sha256"])
        self.assertEqual(readback.readback(self.organization_location)["chain_length"], 3)
        self.assertTrue(_published_ref_absent())
        self.assertNotIn("authentic", json.dumps(closed).lower())


if __name__ == "__main__":
    unittest.main()
