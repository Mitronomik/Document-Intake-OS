from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from spikes.windows_encryption.acl_probe import (
    WELL_KNOWN_ADMINISTRATORS,
    WELL_KNOWN_SYSTEM,
    WELL_KNOWN_USERS,
    AclEvidence,
    _remove_directory,
    acl_failure_reason,
    evaluate_acl_rules,
    probe_directory_is_removed,
    run_acl_probe,
)
from spikes.windows_encryption.run import _acl_checks, _reason
from spikes.windows_encryption.safe_report import (
    ALLOWED_REASON_CODES,
    ResultStatus,
    SafeReport,
    report_to_json,
)

CURRENT_USER = "S-1-5-21-1000"


def _rules() -> dict[str, list[str]]:
    return {
        CURRENT_USER: ["FullControl"],
        WELL_KNOWN_SYSTEM: ["FullControl"],
        WELL_KNOWN_ADMINISTRATORS: ["FullControl"],
    }


def test_acl_probe_returns_stable_status_and_no_raw_output() -> None:
    result = run_acl_probe()
    if platform.system() != "Windows":
        assert result.status == "UNSUPPORTED_NON_WINDOWS"
    else:
        assert result.status in {
            "PASS",
            "ERR_ACL_CURRENT_USER_RIGHTS",
            "ERR_ACL_SYSTEM_RIGHTS",
            "ERR_ACL_ADMINISTRATORS_RIGHTS",
            "ERR_ACL_BROAD_WRITE",
            "ERR_ACL_CLEANUP_FAILED",
            "ERR_ACL_PROBE_FAILED",
            "ERR_ACL_SID_LOOKUP",
            "ERR_ACL_APPLY_INHERITANCE",
            "ERR_ACL_APPLY_SYSTEM",
            "ERR_ACL_APPLY_ADMINISTRATORS",
            "ERR_ACL_APPLY_CURRENT_USER",
            "ERR_ACL_POWERSHELL_LAUNCH",
            "ERR_ACL_READ",
            "ERR_ACL_NORMALIZE_TO_SID",
            "ERR_ACL_JSON_SERIALIZE",
            "ERR_ACL_JSON_PARSE",
            "ERR_ACL_RESULT_SHAPE",
            "ERR_ACL_UNEXPECTED",
        }
    assert "S-" not in repr(result)
    assert "icacls" not in repr(result).lower()


def test_stage_sid_lookup_parser_accepts_bom_and_rejects_bad_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(acl_probe, "_run_powershell", lambda _script: "\ufeff  S-1-5-21-1000  ")
    assert acl_probe._current_user_sid() == CURRENT_USER
    for output in ("", "not-a-sid", "S-1-5-21-1000\nS-1-5-21-2000"):
        monkeypatch.setattr(acl_probe, "_run_powershell", lambda _script, value=output: value)
        try:
            acl_probe._current_user_sid()
        except Exception as exc:
            failure = cast(Any, exc)
            assert failure.reason_code == "ERR_ACL_SID_LOOKUP"
        else:
            raise AssertionError("SID lookup should fail")


def test_acl_application_failures_map_to_specific_reasons(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from spikes.windows_encryption import acl_probe

    expected = [
        "ERR_ACL_APPLY_INHERITANCE",
        "ERR_ACL_APPLY_SYSTEM",
        "ERR_ACL_APPLY_ADMINISTRATORS",
        "ERR_ACL_APPLY_CURRENT_USER",
    ]
    for fail_index, reason in enumerate(expected):
        calls: list[list[str]] = []

        def fake_run(
            _command: list[str],
            calls: list[list[str]] = calls,
            fail_index: int = fail_index,
        ) -> str:
            calls.append(_command)
            if len(calls) == fail_index + 1:
                raise OSError
            return ""

        monkeypatch.setattr(acl_probe, "_run_command", fake_run)
        try:
            acl_probe._apply_acl(tmp_path, CURRENT_USER)
        except Exception as exc:
            failure = cast(Any, exc)
            assert failure.stage == acl_probe.ACL_STAGE_APPLY
            assert failure.reason_code == reason
        else:
            raise AssertionError("ACL application should fail")


def test_acl_inspection_envelope_stage_and_shape_mapping() -> None:
    from spikes.windows_encryption.acl_probe import _rules_from_acl_envelope

    stage_cases = {
        '{"ok":false,"stage":"read"}': "ERR_ACL_READ",
        '{"ok":false,"stage":"normalize"}': "ERR_ACL_NORMALIZE_TO_SID",
        '{"ok":false,"stage":"serialize"}': "ERR_ACL_JSON_SERIALIZE",
        "not json": "ERR_ACL_JSON_PARSE",
        (
            '{"ok":true,"stage":"complete","rules":{"sid":"bad","rights":"FullControl"}}'
        ): "ERR_ACL_RESULT_SHAPE",
    }
    for payload, reason in stage_cases.items():
        try:
            _rules_from_acl_envelope(payload)
        except Exception as exc:
            failure = cast(Any, exc)
            assert failure.reason_code == reason
        else:
            raise AssertionError("ACL envelope should fail")


def test_acl_inspection_envelope_normalizes_singleton_and_multiple_rows() -> None:
    from spikes.windows_encryption.acl_probe import _rules_from_acl_envelope

    singleton = _rules_from_acl_envelope(
        '\ufeff {"ok":true,"stage":"complete","rules":{"sid":"S-1-5-18","rights":"FullControl"}} '
    )
    multiple = _rules_from_acl_envelope(
        '{"ok":true,"stage":"complete","rules":['
        '{"sid":"S-1-5-18","rights":"FullControl"},'
        '{"sid":"S-1-5-18","rights":"Read"}]}'
    )
    assert singleton == {"S-1-5-18": ["FullControl"]}
    assert multiple == {"S-1-5-18": ["FullControl", "Read"]}


def test_stage_failure_yields_not_demonstrated_rights_and_later_stages() -> None:
    from spikes.windows_encryption.acl_probe import AclProbeResult, AclStageResult

    checks = _acl_checks(
        AclProbeResult(
            "ERR_ACL_APPLY_SYSTEM",
            directory_removed=True,
            stages=(
                AclStageResult("acl-stage-current-user-sid", "PASS", "PASS"),
                AclStageResult("acl-stage-apply", "FAIL", "ERR_ACL_APPLY_SYSTEM"),
                AclStageResult("acl-stage-read", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),
                AclStageResult(
                    "acl-stage-normalize-to-sid", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"
                ),
                AclStageResult("acl-stage-json-serialize", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),
                AclStageResult("acl-stage-json-parse", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),
                AclStageResult("acl-directory-cleanup", "PASS", "PASS"),
            ),
        )
    )
    assert checks[1].reason_code == "ERR_ACL_APPLY_SYSTEM"
    assert {check.reason_code for check in checks[6:10]} == {"NOT_DEMONSTRATED"}
    assert not {check.reason_code for check in checks[6:10]} & {
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
    }


def _stage_by_identifier(result: Any, identifier: str) -> Any:
    return {stage.identifier: stage for stage in result.stages}[identifier]


def _assert_later_not_demonstrated(result: Any, failed_identifier: str) -> None:
    from spikes.windows_encryption import acl_probe

    stages = list(acl_probe.ACL_OPERATIONAL_STAGES)
    failed_index = stages.index(failed_identifier)
    by_identifier = {stage.identifier: stage for stage in result.stages}
    for earlier in stages[:failed_index]:
        assert by_identifier[earlier].status == "PASS"
        assert by_identifier[earlier].reason_code == "PASS"
    for later in stages[failed_index + 1 :]:
        assert by_identifier[later].status == "NOT_DEMONSTRATED"
        assert by_identifier[later].reason_code == "NOT_DEMONSTRATED"
    assert not result.rights_evaluated


def test_run_acl_probe_non_windows_reports_unsupported_stages_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Linux")
    result = acl_probe.run_acl_probe()

    assert result.status == "UNSUPPORTED_NON_WINDOWS"
    assert result.directory_removed is True
    assert [stage.identifier for stage in result.stages] == list(acl_probe.ACL_STAGES)
    for stage in result.stages[:-1]:
        assert stage.status == "UNSUPPORTED"
        assert stage.reason_code == "UNSUPPORTED_NON_WINDOWS"
    assert result.stages[-1].identifier == "acl-directory-cleanup"
    assert result.stages[-1].status == "PASS"
    assert result.stages[-1].reason_code == "PASS"


def test_run_acl_probe_non_windows_reports_failed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Linux")
    monkeypatch.setattr(acl_probe, "_remove_directory", lambda _path: False)
    result = acl_probe.run_acl_probe()

    assert result.status == "UNSUPPORTED_NON_WINDOWS"
    assert result.directory_removed is False
    cleanup = _stage_by_identifier(result, "acl-directory-cleanup")
    assert cleanup.status == "FAIL"
    assert cleanup.reason_code == "ERR_ACL_CLEANUP_FAILED"
    for stage in result.stages[:-1]:
        assert stage.status == "UNSUPPORTED"
        assert stage.reason_code == "UNSUPPORTED_NON_WINDOWS"


def test_run_acl_probe_unexpected_sid_stage_maps_to_sid_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Windows")
    monkeypatch.setattr(acl_probe, "_current_user_sid", lambda: (_ for _ in ()).throw(RuntimeError))
    result = acl_probe.run_acl_probe()

    failed = _stage_by_identifier(result, "acl-stage-current-user-sid")
    assert failed.status == "FAIL"
    assert failed.reason_code == "ERR_ACL_UNEXPECTED"
    _assert_later_not_demonstrated(result, "acl-stage-current-user-sid")
    assert _stage_by_identifier(result, "acl-directory-cleanup").reason_code == "PASS"


def test_run_acl_probe_unexpected_apply_stage_maps_to_apply_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Windows")
    monkeypatch.setattr(acl_probe, "_current_user_sid", lambda: CURRENT_USER)
    monkeypatch.setattr(
        acl_probe, "_apply_acl", lambda _path, _sid: (_ for _ in ()).throw(RuntimeError)
    )
    result = acl_probe.run_acl_probe()

    failed = _stage_by_identifier(result, "acl-stage-apply")
    assert failed.status == "FAIL"
    assert failed.reason_code == "ERR_ACL_UNEXPECTED"
    _assert_later_not_demonstrated(result, "acl-stage-apply")
    assert _stage_by_identifier(result, "acl-directory-cleanup").reason_code == "PASS"


def test_run_acl_probe_unexpected_inspection_stage_maps_to_read_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Windows")
    monkeypatch.setattr(acl_probe, "_current_user_sid", lambda: CURRENT_USER)
    monkeypatch.setattr(acl_probe, "_apply_acl", lambda _path, _sid: None)
    monkeypatch.setattr(
        acl_probe, "_acl_inspection_output", lambda _path: (_ for _ in ()).throw(RuntimeError)
    )
    result = acl_probe.run_acl_probe()

    failed = _stage_by_identifier(result, "acl-stage-read")
    assert failed.status == "FAIL"
    assert failed.reason_code == "ERR_ACL_UNEXPECTED"
    _assert_later_not_demonstrated(result, "acl-stage-read")
    assert _stage_by_identifier(result, "acl-directory-cleanup").reason_code == "PASS"


def test_run_acl_probe_unexpected_parse_stage_maps_to_json_parse_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Windows")
    monkeypatch.setattr(acl_probe, "_current_user_sid", lambda: CURRENT_USER)
    monkeypatch.setattr(acl_probe, "_apply_acl", lambda _path, _sid: None)
    monkeypatch.setattr(acl_probe, "_acl_inspection_output", lambda _path: "{}")
    monkeypatch.setattr(
        acl_probe, "_rules_from_acl_envelope", lambda _output: (_ for _ in ()).throw(RuntimeError)
    )
    result = acl_probe.run_acl_probe()

    failed = _stage_by_identifier(result, "acl-stage-json-parse")
    assert failed.status == "FAIL"
    assert failed.reason_code == "ERR_ACL_UNEXPECTED"
    _assert_later_not_demonstrated(result, "acl-stage-json-parse")
    assert _stage_by_identifier(result, "acl-directory-cleanup").reason_code == "PASS"


def test_run_acl_probe_expected_stage_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spikes.windows_encryption import acl_probe

    monkeypatch.setattr(cast(Any, acl_probe).platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        acl_probe,
        "_current_user_sid",
        lambda: (_ for _ in ()).throw(
            acl_probe._AclStageFailure("acl-stage-current-user-sid", "ERR_ACL_SID_LOOKUP")
        ),
    )
    result = acl_probe.run_acl_probe()

    failed = _stage_by_identifier(result, "acl-stage-current-user-sid")
    assert failed.status == "FAIL"
    assert failed.reason_code == "ERR_ACL_SID_LOOKUP"
    _assert_later_not_demonstrated(result, "acl-stage-current-user-sid")


def test_acl_inspection_launch_and_process_failures_are_distinct(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from spikes.windows_encryption import acl_probe

    def raise_file_not_found(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError

    monkeypatch.setattr(cast(Any, acl_probe).subprocess, "run", raise_file_not_found)
    try:
        acl_probe._run_powershell("safe-script")
    except Exception as exc:
        failure = cast(Any, exc)
        assert failure.stage == "acl-stage-read"
        assert failure.reason_code == "ERR_ACL_POWERSHELL_LAUNCH"
    else:
        raise AssertionError("PowerShell launch should fail")

    def raise_process_failure(_script: str, env: Any = None) -> str:
        raise subprocess.CalledProcessError(1, ["powershell.exe"], output="raw", stderr="secret")

    monkeypatch.setattr(acl_probe, "_run_powershell", raise_process_failure)
    try:
        acl_probe._acl_inspection_output(tmp_path)
    except Exception as exc:
        failure = cast(Any, exc)
        assert failure.stage == "acl-stage-read"
        assert failure.reason_code == "ERR_ACL_READ"
        assert "raw" not in repr(failure)
        assert "secret" not in repr(failure)
        assert str(tmp_path) not in repr(failure)
        assert "S-" not in repr(failure)
    else:
        raise AssertionError("PowerShell process failure should fail")


def test_acl_probe_cleans_up_directory() -> None:
    assert probe_directory_is_removed()


def test_current_user_failure_maps_to_specific_reason() -> None:
    rules = _rules()
    rules.pop(CURRENT_USER)
    evidence = evaluate_acl_rules(rules, CURRENT_USER)
    assert acl_failure_reason(evidence) == "ERR_ACL_CURRENT_USER_RIGHTS"
    assert _acl_checks_from(evidence)[0].reason_code == "ERR_ACL_CURRENT_USER_RIGHTS"


def test_system_failure_maps_to_specific_reason() -> None:
    rules = _rules()
    rules.pop(WELL_KNOWN_SYSTEM)
    evidence = evaluate_acl_rules(rules, CURRENT_USER)
    assert acl_failure_reason(evidence) == "ERR_ACL_SYSTEM_RIGHTS"
    assert _acl_checks_from(evidence)[1].reason_code == "ERR_ACL_SYSTEM_RIGHTS"


def test_administrators_failure_maps_to_specific_reason() -> None:
    rules = _rules()
    rules.pop(WELL_KNOWN_ADMINISTRATORS)
    evidence = evaluate_acl_rules(rules, CURRENT_USER)
    assert acl_failure_reason(evidence) == "ERR_ACL_ADMINISTRATORS_RIGHTS"
    assert _acl_checks_from(evidence)[2].reason_code == "ERR_ACL_ADMINISTRATORS_RIGHTS"


def test_one_missing_required_principal_fails_even_when_other_two_pass() -> None:
    rules = {
        CURRENT_USER: ["FullControl"],
        WELL_KNOWN_SYSTEM: ["FullControl"],
    }
    evidence = evaluate_acl_rules(rules, CURRENT_USER)
    assert evidence.current_user_rights
    assert evidence.system_rights
    assert not evidence.administrators_rights
    assert acl_failure_reason(evidence) == "ERR_ACL_ADMINISTRATORS_RIGHTS"


def test_broad_write_maps_to_specific_reason() -> None:
    rules = _rules()
    rules[WELL_KNOWN_USERS] = ["ReadAndExecute, Write"]
    evidence = evaluate_acl_rules(rules, CURRENT_USER)
    assert not evidence.broad_write_blocked
    assert acl_failure_reason(evidence) == "ERR_ACL_BROAD_WRITE"
    assert _acl_checks_from(evidence)[3].reason_code == "ERR_ACL_BROAD_WRITE"


def test_all_three_required_principals_must_pass() -> None:
    for missing_sid in (CURRENT_USER, WELL_KNOWN_SYSTEM, WELL_KNOWN_ADMINISTRATORS):
        rules = _rules()
        rules.pop(missing_sid)
        evidence = evaluate_acl_rules(rules, CURRENT_USER)
        assert not all(
            (
                evidence.current_user_rights,
                evidence.system_rights,
                evidence.administrators_rights,
            )
        )


def test_successful_directory_deletion_produces_cleanup_pass(tmp_path: Path) -> None:
    temp_root = tmp_path / "acl-cleanup"
    temp_root.mkdir()
    removed = _remove_directory(temp_root)
    checks = _acl_checks_from(AclEvidence(True, True, True, True), directory_removed=removed)
    assert checks[4].identifier == "acl-directory-cleanup"
    assert checks[4].status == ResultStatus.PASS
    assert checks[4].reason_code == "PASS"


def test_failed_directory_deletion_produces_cleanup_failure(tmp_path: Path) -> None:
    temp_root = tmp_path / "acl-cleanup"
    temp_root.mkdir()
    removed = _remove_directory(temp_root, rmtree=lambda _path: (_ for _ in ()).throw(OSError()))
    checks = _acl_checks_from(AclEvidence(True, True, True, True), directory_removed=removed)
    assert checks[4].identifier == "acl-directory-cleanup"
    assert checks[4].status == ResultStatus.FAIL
    assert checks[4].reason_code == "ERR_ACL_CLEANUP_FAILED"


def test_acl_reason_codes_survive_reason_mapping() -> None:
    codes = {
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
        "ERR_ACL_BROAD_WRITE",
        "ERR_ACL_CLEANUP_FAILED",
        "ERR_ACL_PROBE_FAILED",
        "ERR_ACL_SID_LOOKUP",
        "ERR_ACL_APPLY_INHERITANCE",
        "ERR_ACL_APPLY_SYSTEM",
        "ERR_ACL_APPLY_ADMINISTRATORS",
        "ERR_ACL_APPLY_CURRENT_USER",
        "ERR_ACL_POWERSHELL_LAUNCH",
        "ERR_ACL_READ",
        "ERR_ACL_NORMALIZE_TO_SID",
        "ERR_ACL_JSON_SERIALIZE",
        "ERR_ACL_JSON_PARSE",
        "ERR_ACL_RESULT_SHAPE",
        "ERR_ACL_UNEXPECTED",
    }
    assert {_reason(code) for code in codes} == codes


def test_acl_reason_codes_are_allowlisted() -> None:
    assert {
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
        "ERR_ACL_BROAD_WRITE",
        "ERR_ACL_CLEANUP_FAILED",
        "ERR_ACL_PROBE_FAILED",
        "ERR_ACL_SID_LOOKUP",
        "ERR_ACL_APPLY_INHERITANCE",
        "ERR_ACL_APPLY_SYSTEM",
        "ERR_ACL_APPLY_ADMINISTRATORS",
        "ERR_ACL_APPLY_CURRENT_USER",
        "ERR_ACL_POWERSHELL_LAUNCH",
        "ERR_ACL_READ",
        "ERR_ACL_NORMALIZE_TO_SID",
        "ERR_ACL_JSON_SERIALIZE",
        "ERR_ACL_JSON_PARSE",
        "ERR_ACL_RESULT_SHAPE",
        "ERR_ACL_UNEXPECTED",
    } <= ALLOWED_REASON_CODES


def test_raw_sid_acl_output_and_absolute_paths_absent_from_serialized_reports(
    tmp_path: Path,
) -> None:
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T12:00:00+00:00",
        os_family="Windows",
        os_release="Server2022",
        architecture="AMD64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
        checks=_acl_checks_from(AclEvidence(True, True, True, True)),
        recommendation="CONDITIONALLY_FEASIBLE",
    )
    text = report_to_json(report)
    assert CURRENT_USER not in text
    assert "icacls" not in text.lower()
    assert "BUILTIN" not in text
    assert str(tmp_path) not in text
    json.loads(text)


def _acl_checks_from(evidence: AclEvidence, directory_removed: bool = True):  # type: ignore[no-untyped-def]
    from spikes.windows_encryption.acl_probe import AclProbeResult

    return _acl_checks(
        AclProbeResult(
            "PASS",
            current_user_rights=evidence.current_user_rights,
            system_rights=evidence.system_rights,
            administrators_rights=evidence.administrators_rights,
            broad_write_blocked=evidence.broad_write_blocked,
            directory_removed=directory_removed,
            rights_evaluated=True,
        )
    )


def test_cleanup_check_depends_only_on_directory_removed_for_pass_status() -> None:
    checks = _acl_checks_from(AclEvidence(True, True, True, True), directory_removed=False)
    assert checks[4].identifier == "acl-directory-cleanup"
    assert checks[4].status == ResultStatus.FAIL
    assert checks[4].reason_code == "ERR_ACL_CLEANUP_FAILED"


def test_cleanup_check_independent_for_probe_failure() -> None:
    from spikes.windows_encryption.acl_probe import AclProbeResult

    removed_checks = _acl_checks(AclProbeResult("ERR_ACL_PROBE_FAILED", directory_removed=True))
    failed_checks = _acl_checks(AclProbeResult("ERR_ACL_PROBE_FAILED", directory_removed=False))

    assert [check.reason_code for check in removed_checks[:4]] == ["NOT_DEMONSTRATED"] * 4
    assert removed_checks[4].status == ResultStatus.PASS
    assert removed_checks[4].reason_code == "PASS"
    assert failed_checks[4].status == ResultStatus.FAIL
    assert failed_checks[4].reason_code == "ERR_ACL_CLEANUP_FAILED"


def test_cleanup_check_independent_for_unsupported_non_windows() -> None:
    from spikes.windows_encryption.acl_probe import AclProbeResult

    removed_checks = _acl_checks(AclProbeResult("UNSUPPORTED_NON_WINDOWS", directory_removed=True))
    failed_checks = _acl_checks(AclProbeResult("UNSUPPORTED_NON_WINDOWS", directory_removed=False))

    assert [check.status for check in removed_checks[:4]] == [ResultStatus.UNSUPPORTED] * 4
    assert [check.reason_code for check in removed_checks[:4]] == ["UNSUPPORTED_NON_WINDOWS"] * 4
    assert removed_checks[4].status == ResultStatus.PASS
    assert removed_checks[4].reason_code == "PASS"
    assert failed_checks[4].status == ResultStatus.FAIL
    assert failed_checks[4].reason_code == "ERR_ACL_CLEANUP_FAILED"


def test_cleanup_check_independent_when_principal_check_fails() -> None:
    checks = _acl_checks_from(AclEvidence(False, True, True, True), directory_removed=True)
    assert checks[0].status == ResultStatus.FAIL
    assert checks[0].reason_code == "ERR_ACL_CURRENT_USER_RIGHTS"
    assert checks[4].status == ResultStatus.PASS
    assert checks[4].reason_code == "PASS"


def test_broad_write_capable_rights_are_blocked() -> None:
    for right in ("WriteData", "AppendData", "WriteAttributes", "Modify", "FullControl"):
        rules = _rules()
        rules[WELL_KNOWN_USERS] = [f"ReadAndExecute, {right}"]
        evidence = evaluate_acl_rules(rules, CURRENT_USER)
        assert not evidence.broad_write_blocked, right
        assert acl_failure_reason(evidence) == "ERR_ACL_BROAD_WRITE"


def test_read_only_broad_principal_rights_are_allowed() -> None:
    for right in ("Read", "ReadAndExecute", "ListDirectory"):
        rules = _rules()
        rules[WELL_KNOWN_USERS] = [right]
        evidence = evaluate_acl_rules(rules, CURRENT_USER)
        assert evidence.broad_write_blocked, right
        assert acl_failure_reason(evidence) == "PASS"
