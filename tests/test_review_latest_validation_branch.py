"""Tests for cf019: review/latest validation branch contract support."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))

from validation_branch import (  # noqa: E402
    CI_BILLING_FAILURE,
    CI_FAIL,
    CI_NO_LOG_STARTUP,
    CI_PASS,
    CI_SKIPPED,
    CI_UNKNOWN,
    DEFAULT_VALIDATION_BRANCH,
    ValidationBranchContract,
    build_delivery_guidance,
    classify_ci_status,
    contract_from_dict,
    is_ci_nonblocking_for_premerge,
)


# ---------------------------------------------------------------------------
# Default validation branch
# ---------------------------------------------------------------------------

def test_default_validation_branch_is_review_latest():
    assert DEFAULT_VALIDATION_BRANCH == "review/latest"


def test_contract_default_branch_is_review_latest():
    c = ValidationBranchContract()
    assert c.branch == "review/latest"


# ---------------------------------------------------------------------------
# CI status classification
# ---------------------------------------------------------------------------

def test_classify_ci_status_returns_unknown_for_empty():
    assert classify_ci_status(None) == CI_UNKNOWN
    assert classify_ci_status("") == CI_UNKNOWN


def test_classify_ci_status_detects_no_log():
    assert classify_ci_status("Error: no log available") == CI_NO_LOG_STARTUP
    assert classify_ci_status("No log files found") == CI_NO_LOG_STARTUP


def test_classify_ci_status_detects_billing():
    assert classify_ci_status("You have exceeded your free minutes") == CI_NO_LOG_STARTUP
    assert classify_ci_status("billing limit reached") == CI_NO_LOG_STARTUP
    assert classify_ci_status("Actions usage limit exceeded") == CI_NO_LOG_STARTUP


def test_classify_ci_status_detects_startup_failure():
    assert classify_ci_status("startup failure on runner") == CI_NO_LOG_STARTUP


def test_classify_ci_status_returns_fail_for_real_failure():
    assert classify_ci_status("3 tests failed") == CI_FAIL
    assert classify_ci_status("FAILED tests/test_foo.py::test_bar") == CI_FAIL


# ---------------------------------------------------------------------------
# CI non-blocking classification
# ---------------------------------------------------------------------------

def test_is_ci_nonblocking_no_log_startup():
    assert is_ci_nonblocking_for_premerge(CI_NO_LOG_STARTUP) is True


def test_is_ci_nonblocking_billing():
    assert is_ci_nonblocking_for_premerge(CI_BILLING_FAILURE) is True


def test_is_ci_nonblocking_skipped():
    assert is_ci_nonblocking_for_premerge(CI_SKIPPED) is True


def test_is_ci_nonblocking_unknown():
    assert is_ci_nonblocking_for_premerge(CI_UNKNOWN) is True


def test_is_ci_nonblocking_pass_is_blocking():
    assert is_ci_nonblocking_for_premerge(CI_PASS) is False


def test_is_ci_nonblocking_fail_is_blocking():
    assert is_ci_nonblocking_for_premerge(CI_FAIL) is False


# ---------------------------------------------------------------------------
# ValidationBranchContract fields and validation
# ---------------------------------------------------------------------------

def test_contract_required_fields_missing():
    c = ValidationBranchContract()
    ok, missing = c.validate()
    assert not ok
    assert "commit_hash" in missing


def test_contract_valid_when_commit_present():
    c = ValidationBranchContract(branch="review/latest", commit_hash="abc123")
    ok, missing = c.validate()
    assert ok
    assert missing == []


def test_contract_has_conflicts_property():
    c = ValidationBranchContract()
    assert not c.has_conflicts
    c.conflict_files.append("apps/web/src/foo.ts")
    assert c.has_conflicts


def test_contract_is_ci_nonblocking_property():
    c = ValidationBranchContract(ci_status=CI_NO_LOG_STARTUP)
    assert c.is_ci_nonblocking
    c2 = ValidationBranchContract(ci_status=CI_FAIL)
    assert not c2.is_ci_nonblocking


def test_contract_to_dict():
    c = ValidationBranchContract(
        branch="review/latest",
        commit_hash="def456",
        tests_run=["pytest tests/ -q"],
        ci_status=CI_PASS,
    )
    d = c.to_dict()
    assert d["branch"] == "review/latest"
    assert d["commit_hash"] == "def456"
    assert d["ci_status"] == CI_PASS
    assert d["has_conflicts"] is False
    assert d["is_ci_nonblocking"] is False


def test_contract_from_dict_round_trip():
    original = ValidationBranchContract(
        branch="review/latest",
        commit_hash="abc789",
        tests_run=["npm test"],
        conflict_files=["src/index.ts"],
        unresolved_risks=["auth not reviewed"],
        ci_status=CI_NO_LOG_STARTUP,
    )
    restored = contract_from_dict(original.to_dict())
    assert restored.branch == original.branch
    assert restored.commit_hash == original.commit_hash
    assert restored.tests_run == original.tests_run
    assert restored.conflict_files == original.conflict_files
    assert restored.unresolved_risks == original.unresolved_risks
    assert restored.ci_status == original.ci_status


# ---------------------------------------------------------------------------
# build_delivery_guidance output
# ---------------------------------------------------------------------------

def test_delivery_guidance_contains_branch_and_commit():
    c = ValidationBranchContract(branch="review/latest", commit_hash="abc123", ci_status=CI_PASS)
    text = build_delivery_guidance(c)
    assert "review/latest" in text
    assert "abc123" in text


def test_delivery_guidance_warns_when_commit_missing():
    c = ValidationBranchContract(branch="review/latest")
    text = build_delivery_guidance(c)
    assert "REQUIRED" in text


def test_delivery_guidance_warns_on_nonblocking_ci():
    c = ValidationBranchContract(
        branch="review/latest",
        commit_hash="abc",
        ci_status=CI_NO_LOG_STARTUP,
    )
    text = build_delivery_guidance(c)
    assert "non-blocking" in text
    assert "local validation" in text


def test_delivery_guidance_no_nonblocking_warning_on_pass():
    c = ValidationBranchContract(branch="review/latest", commit_hash="abc", ci_status=CI_PASS)
    text = build_delivery_guidance(c)
    assert "non-blocking" not in text


def test_delivery_guidance_lists_tests_run():
    c = ValidationBranchContract(
        branch="review/latest", commit_hash="abc",
        tests_run=["pytest tests/ -q", "npm test"],
        ci_status=CI_PASS,
    )
    text = build_delivery_guidance(c)
    assert "pytest tests/ -q" in text
    assert "npm test" in text


def test_delivery_guidance_lists_conflict_files():
    c = ValidationBranchContract(
        branch="review/latest", commit_hash="abc",
        conflict_files=["apps/web/src/index.ts"],
        ci_status=CI_PASS,
    )
    text = build_delivery_guidance(c)
    assert "apps/web/src/index.ts" in text
    assert "Merge conflicts" in text


def test_delivery_guidance_lists_unresolved_risks():
    c = ValidationBranchContract(
        branch="review/latest", commit_hash="abc",
        unresolved_risks=["auth boundary not reviewed"],
        ci_status=CI_PASS,
    )
    text = build_delivery_guidance(c)
    assert "auth boundary not reviewed" in text
    assert "Unresolved risks" in text


def test_delivery_guidance_main_protection_note():
    c = ValidationBranchContract(branch="review/latest", commit_hash="abc", ci_status=CI_PASS)
    text = build_delivery_guidance(c)
    assert "main is protected" in text.lower() or "main" in text


# ---------------------------------------------------------------------------
# No-log CI scenario (core policy test)
# ---------------------------------------------------------------------------

def test_nolog_ci_does_not_block_premerge_validation():
    """GitHub no-log startup failure must NOT block pre-main operator validation."""
    ci_output = "Error: no log — workflow file not found, startup failure"
    status = classify_ci_status(ci_output)
    assert status == CI_NO_LOG_STARTUP
    assert is_ci_nonblocking_for_premerge(status) is True
    # Operator can still validate locally
    c = ValidationBranchContract(
        branch="review/latest",
        commit_hash="deadbeef",
        ci_status=status,
    )
    assert c.is_ci_nonblocking
    guidance = build_delivery_guidance(c)
    assert "non-blocking" in guidance
