"""Every `uses:` in .github/workflows must be pinned to a 40-hex commit sha.

Local actions (`./...`) are exempt. Stdlib only.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)")
PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def unpinned_uses():
    found = []
    for path in sorted(list(WORKFLOWS.rglob("*.yml")) + list(WORKFLOWS.rglob("*.yaml"))):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            m = USES.match(line)
            if not m:
                continue
            ref = m.group(1)
            if ref.startswith("./") or PINNED.match(ref):
                continue
            found.append(f"{path.relative_to(ROOT)}:{lineno}: {ref}")
    return found


class WorkflowActionPinsTest(unittest.TestCase):
    def test_workflows_exist(self):
        self.assertTrue(any(WORKFLOWS.glob("*.y*ml")), "no workflows found under .github/workflows")

    def test_every_uses_is_pinned_to_full_sha(self):
        bad = unpinned_uses()
        self.assertEqual(bad, [], "\n".join([
            "failure_code: WORKFLOW_ACTION_NOT_PINNED",
            "failed_predicate: every non-local `uses:` in .github/workflows/** matches <action>@<40-hex sha>; unpinned: "
            + "; ".join(bad),
            "required_evidence_or_repair: pin each listed `uses:` to the sha from "
            "`git ls-remote https://github.com/<owner>/<action> refs/tags/<tag>` (peel annotated tags with ^{}), "
            "keeping the tag as a trailing `# <tag>` comment",
            "retry_entrypoint: python3 -m unittest -v tests.test_workflow_action_pins",
            "owning_existing_goal: SVORG-LLM-ORG-FOUNDATION-001",
            "next_attempt: re-run the retry_entrypoint after pinning the listed references",
        ]))


if __name__ == "__main__":
    unittest.main()
