"""A ledger store on a git ref, held to the POSIX store's behaviour.

These runs use temporary bare repositories only. They are not authentic
production receipts, and no location here is the published organization ledger.
Authority and time are constraint variables. A disposition is transition
evidence only.
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger_store = _load("git_ledger_store", "resident-runtime/ledger_store.py")

REF = "refs/test/ledger"
DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def git(repository_path, *args, stdin=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_DIR=str(repository_path), GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@invalid",
               GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@invalid")
    return subprocess.run(["git", *args], input=stdin, capture_output=True, check=True, env=env).stdout


def tree(repository_path, ref=REF):
    listed = git(repository_path, "ls-tree", "-r", "-z", "--name-only", ref)
    return {name for name in listed.decode().split("\0") if name}


class _Work(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.work = Path(self._dir.name)
        self.repo = self.work / "ledger.git"

    def git_store(self, ref=REF):
        store = ledger_store.GitLedgerStore(self.repo, ref)
        store.initialize()
        return store


class ParityWithPosixTests(_Work):
    def test_every_operation_answers_as_the_posix_store_does(self):
        posix = ledger_store.PosixLedgerStore(self.work / "posix")
        posix.initialize()
        git_store = self.git_store()
        head = ledger_store.HEAD_KEY
        receipt = ledger_store.receipt_key(DIGEST)
        source = ledger_store.source_key(OTHER)
        steps = [
            ("get", (head,)),
            ("exists", (head,)),
            ("list_prefix", (ledger_store.RECEIPT_PREFIX,)),
            ("compare_and_swap", (head, None, {"receipt_sha256": DIGEST})),
            ("compare_and_swap", (head, None, {"receipt_sha256": OTHER})),
            ("put", (receipt, {"receipt_sha256": DIGEST, "nested": {"n": [1, 2]}})),
            ("get", (receipt,)),
            ("exists", (receipt,)),
            ("append_transaction", (ledger_store.receipt_key(OTHER), {"receipt_sha256": OTHER},
                                    {"receipt_sha256": "sha256:" + "c" * 64}, {"receipt_sha256": OTHER})),
            ("append_transaction", (ledger_store.receipt_key(OTHER), {"receipt_sha256": OTHER},
                                    {"receipt_sha256": DIGEST}, {"receipt_sha256": OTHER},
                                    {source: {"source": True}})),
            ("get", (head,)),
            ("get", (source,)),
            ("list_prefix", (ledger_store.RECEIPT_PREFIX,)),
            ("list_prefix", (ledger_store.SOURCE_PREFIX,)),
            ("list_prefix", ("absent/",)),
        ]
        for name, args in steps:
            with self.subTest(name, args=args):
                self.assertEqual(getattr(git_store, name)(*args), getattr(posix, name)(*args))

    def test_a_document_is_stored_as_the_bytes_a_posix_root_holds(self):
        posix = ledger_store.PosixLedgerStore(self.work / "posix")
        git_store = self.git_store()
        for store in (posix, git_store):
            store.put(ledger_store.HEAD_KEY, {"b": 2, "a": 1})
        self.assertEqual(git(self.repo, "cat-file", "blob", REF + ":HEAD.json"),
                         (self.work / "posix" / "HEAD.json").read_bytes())

    def test_head_and_receipts_land_at_the_keys_a_posix_root_uses(self):
        git_store = self.git_store()
        self.assertTrue(git_store.append_transaction(
            ledger_store.receipt_key(DIGEST), {"receipt_sha256": DIGEST}, None,
            {"receipt_sha256": DIGEST},
            {ledger_store.source_key(OTHER): {"source": True}}))
        self.assertEqual(tree(self.repo), {
            "HEAD.json",
            "receipts/" + "a" * 64 + ".json",
            "source-receipts/" + "b" * 64 + ".json",
        })

    def test_a_transaction_is_one_commit(self):
        git_store = self.git_store()
        git_store.append_transaction(
            ledger_store.receipt_key(DIGEST), {"receipt_sha256": DIGEST}, None,
            {"receipt_sha256": DIGEST})
        git_store.append_transaction(
            ledger_store.receipt_key(OTHER), {"receipt_sha256": OTHER},
            {"receipt_sha256": DIGEST}, {"receipt_sha256": OTHER})
        self.assertEqual(git(self.repo, "rev-list", "--count", REF).strip(), b"2")


class CompareAndSwapRaceTests(_Work):
    def test_a_writer_that_loses_the_ref_comparison_publishes_nothing(self):
        mine = self.git_store()
        competitor = ledger_store.GitLedgerStore(self.repo, REF)
        competitor.exclusive = nullcontext
        mine.put(ledger_store.receipt_key(DIGEST), {"receipt_sha256": DIGEST})
        mine.put(ledger_store.HEAD_KEY, {"receipt_sha256": DIGEST})
        theirs_key = ledger_store.receipt_key("sha256:" + "c" * 64)
        mine_key = ledger_store.receipt_key(OTHER)
        publish = mine._publish

        def interleaved(new, expected):
            self.assertTrue(competitor.append_transaction(
                theirs_key, {"receipt_sha256": "sha256:" + "c" * 64},
                {"receipt_sha256": DIGEST}, {"receipt_sha256": "sha256:" + "c" * 64}))
            mine._publish = publish
            return publish(new, expected)

        mine._publish = interleaved
        won = mine.append_transaction(
            mine_key, {"receipt_sha256": OTHER},
            {"receipt_sha256": DIGEST}, {"receipt_sha256": OTHER})
        self.assertIs(won, False)
        self.assertEqual(mine.get(ledger_store.HEAD_KEY), {"receipt_sha256": "sha256:" + "c" * 64})
        self.assertNotIn(mine_key, tree(self.repo))
        self.assertIn(theirs_key, tree(self.repo))

    def test_a_stale_view_returns_false_and_leaves_the_ref_where_it_was(self):
        store = self.git_store()
        store.put(ledger_store.HEAD_KEY, {"receipt_sha256": DIGEST})
        before = git(self.repo, "rev-parse", REF)
        self.assertIs(store.append_transaction(
            ledger_store.receipt_key(OTHER), {"receipt_sha256": OTHER},
            None, {"receipt_sha256": OTHER}), False)
        self.assertIs(store.compare_and_swap(ledger_store.HEAD_KEY, None, {"receipt_sha256": OTHER}), False)
        self.assertEqual(git(self.repo, "rev-parse", REF), before)


class ReceiptImmutabilityTests(_Work):
    def test_a_receipt_cannot_be_replaced_with_different_content(self):
        store = self.git_store()
        for key in (ledger_store.receipt_key(DIGEST), ledger_store.source_key(DIGEST)):
            with self.subTest(key):
                store.put(key, {"receipt_sha256": DIGEST})
                before = git(self.repo, "rev-parse", REF)
                with self.assertRaisesRegex(ValueError, "ledger_receipt_collision"):
                    store.put(key, {"receipt_sha256": DIGEST, "edited": True})
                self.assertEqual(store.get(key), {"receipt_sha256": DIGEST})
                self.assertEqual(git(self.repo, "rev-parse", REF), before)

    def test_head_is_not_immutable(self):
        store = self.git_store()
        store.put(ledger_store.HEAD_KEY, {"receipt_sha256": DIGEST})
        store.put(ledger_store.HEAD_KEY, {"receipt_sha256": OTHER})
        self.assertEqual(store.get(ledger_store.HEAD_KEY), {"receipt_sha256": OTHER})

    def test_a_colliding_append_writes_nothing(self):
        store = self.git_store()
        key = ledger_store.receipt_key(DIGEST)
        store.append_transaction(key, {"receipt_sha256": DIGEST}, None, {"receipt_sha256": DIGEST})
        before = git(self.repo, "rev-parse", REF)
        with self.assertRaisesRegex(ValueError, "ledger_receipt_collision"):
            store.append_transaction(key, {"receipt_sha256": DIGEST, "edited": True},
                                     {"receipt_sha256": DIGEST}, {"receipt_sha256": OTHER})
        self.assertEqual(git(self.repo, "rev-parse", REF), before)


class SuppliedLocationTests(_Work):
    def test_a_plain_path_still_opens_the_posix_store(self):
        located = ledger_store.parse_locator(str(self.work / "posix"))
        self.assertEqual(located, (self.work / "posix").resolve())
        self.assertIsInstance(ledger_store.open_store(located), ledger_store.PosixLedgerStore)

    def test_a_git_locator_must_name_both_a_repository_and_a_qualified_ref(self):
        for text in ("git+" + str(self.repo), "git+" + str(self.repo) + "#",
                     "git+" + str(self.repo) + "#ledger",
                     "git+" + str(self.repo) + "#refs/bad..ref"):
            with self.subTest(text):
                with self.assertRaises(ledger_store.LedgerLocatorInvalid):
                    ledger_store.parse_locator(text)
        self.assertFalse(self.repo.exists())

    def test_reading_a_location_that_was_never_initialized_creates_nothing(self):
        subprocess.run(["git", "init", "--quiet", str(self.work)], check=True, capture_output=True)
        store = ledger_store.GitLedgerStore(self.repo, REF)
        self.assertIsNone(store.get(ledger_store.HEAD_KEY))
        self.assertEqual(store.list_prefix(ledger_store.RECEIPT_PREFIX), set())
        self.assertFalse(self.repo.exists())

    def test_the_store_module_names_no_ledger_ref_of_its_own(self):
        source = (ROOT / "resident-runtime/ledger_store.py").read_text()
        for token in ("refs/stegverse", "refs/heads/", "DEFAULT_REF", "DEFAULT_LOCATOR"):
            self.assertNotIn(token, source)
        self.assertNotIn("grant", source.lower())


if __name__ == "__main__":
    unittest.main()
