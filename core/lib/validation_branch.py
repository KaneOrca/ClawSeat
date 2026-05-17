"""ClawSeat validation branch contract support (cf019).

Supports the operator-validation branch flow where approved task work is
merged to a named branch (e.g. review/latest) for local validation before
main.

Policy:
- Approved work merges into the validation branch; main is only updated
  after operator signs off.
- Delivery guidance must carry: branch name, commit hash, tests run,
  conflict files (if any), and unresolved risks.
- GitHub no-log startup/billing CI failures must NOT block pre-main
  operator validation; they are classified as non-blocking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Default validation branch name for Cartooner; projects may override via profile.
DEFAULT_VALIDATION_BRANCH = "review/latest"

# CI status values
CI_PASS = "pass"
CI_FAIL = "fail"
CI_NO_LOG_STARTUP = "no_log_startup_failure"
CI_BILLING_FAILURE = "billing_failure"
CI_SKIPPED = "skipped"
CI_UNKNOWN = "unknown"

# Status values that must NOT block pre-main operator validation
_NONBLOCKING_CI_STATUSES = frozenset({
    CI_NO_LOG_STARTUP,
    CI_BILLING_FAILURE,
    CI_SKIPPED,
    CI_UNKNOWN,
})

# Patterns in CI log output that indicate no-log startup or billing failures
_NO_LOG_PATTERNS = (
    re.compile(r"no\s*log", re.IGNORECASE),
    re.compile(r"billing\s*(limit|failure|block)", re.IGNORECASE),
    re.compile(r"workflow\s*file\s*not\s*found", re.IGNORECASE),
    re.compile(r"startup\s*failure", re.IGNORECASE),
    re.compile(r"you\s*have\s*exceeded\s*your\s*(free\s*)?minutes", re.IGNORECASE),
    re.compile(r"Actions\s*usage\s*limit", re.IGNORECASE),
)


@dataclass
class ValidationBranchContract:
    """Contract for an operator-validation branch merge.

    Planner fills this when merging a task branch into the validation branch.
    Delivery guidance (DELIVERY.md) must include all fields.
    """

    branch: str = DEFAULT_VALIDATION_BRANCH
    commit_hash: str | None = None
    tests_run: list[str] = field(default_factory=list)
    conflict_files: list[str] = field(default_factory=list)
    unresolved_risks: list[str] = field(default_factory=list)
    ci_status: str = CI_UNKNOWN

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflict_files)

    @property
    def is_ci_nonblocking(self) -> bool:
        """True when CI status must not block pre-main operator validation."""
        return is_ci_nonblocking_for_premerge(self.ci_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "tests_run": list(self.tests_run),
            "conflict_files": list(self.conflict_files),
            "unresolved_risks": list(self.unresolved_risks),
            "ci_status": self.ci_status,
            "has_conflicts": self.has_conflicts,
            "is_ci_nonblocking": self.is_ci_nonblocking,
        }

    def validate(self) -> tuple[bool, list[str]]:
        """Check required fields are present. Returns (ok, list_of_missing)."""
        missing = []
        if not self.branch:
            missing.append("branch")
        if not self.commit_hash:
            missing.append("commit_hash")
        return (len(missing) == 0, missing)


def classify_ci_status(failure_text: str | None) -> str:
    """Classify CI output text as a known CI status value.

    Returns CI_NO_LOG_STARTUP when the text indicates a startup/billing
    failure (not a real test failure). Returns CI_FAIL for genuine failures.
    Returns CI_UNKNOWN when text is empty/None.
    """
    if not failure_text:
        return CI_UNKNOWN
    for pattern in _NO_LOG_PATTERNS:
        if pattern.search(failure_text):
            return CI_NO_LOG_STARTUP
    return CI_FAIL


def is_ci_nonblocking_for_premerge(ci_status: str) -> bool:
    """Return True when CI status should NOT block pre-main operator validation.

    No-log startup failures, billing failures, skipped and unknown CI results
    are non-blocking: the operator can proceed with local validation on the
    validation branch without waiting for CI to resolve.
    """
    return ci_status in _NONBLOCKING_CI_STATUSES


def build_delivery_guidance(contract: ValidationBranchContract) -> str:
    """Generate a DELIVERY.md section for the validation branch contract.

    Produces a Markdown block suitable for inclusion in DELIVERY.md. Includes
    a warning when CI is non-blocking so the operator knows to validate locally.
    """
    lines = [
        "## Validation Branch",
        "",
        f"- **Branch**: `{contract.branch}`",
        f"- **Commit**: `{contract.commit_hash or 'REQUIRED — fill before relay'}`",
        f"- **CI status**: `{contract.ci_status}`",
    ]

    if contract.is_ci_nonblocking and contract.ci_status != CI_PASS:
        lines.append(
            f"- **CI note**: `{contract.ci_status}` is non-blocking — "
            "proceed with local validation on validation branch; do not wait for CI."
        )

    if contract.tests_run:
        lines.append("- **Tests run**:")
        for t in contract.tests_run:
            lines.append(f"  - {t}")
    else:
        lines.append("- **Tests run**: none recorded")

    if contract.conflict_files:
        lines.append("- **Merge conflicts** (must resolve before operator sign-off):")
        for f in contract.conflict_files:
            lines.append(f"  - `{f}`")
    else:
        lines.append("- **Merge conflicts**: none")

    if contract.unresolved_risks:
        lines.append("- **Unresolved risks** (planner must address before main):")
        for r in contract.unresolved_risks:
            lines.append(f"  - {r}")
    else:
        lines.append("- **Unresolved risks**: none")

    lines += [
        "",
        "> main is protected until operator validates on "
        f"`{contract.branch}` and signs off.",
    ]
    return "\n".join(lines)


def contract_from_dict(data: dict[str, Any]) -> ValidationBranchContract:
    """Deserialize a ValidationBranchContract from a plain dict."""
    return ValidationBranchContract(
        branch=str(data.get("branch") or DEFAULT_VALIDATION_BRANCH),
        commit_hash=data.get("commit_hash") or None,
        tests_run=list(data.get("tests_run") or []),
        conflict_files=list(data.get("conflict_files") or []),
        unresolved_risks=list(data.get("unresolved_risks") or []),
        ci_status=str(data.get("ci_status") or CI_UNKNOWN),
    )
