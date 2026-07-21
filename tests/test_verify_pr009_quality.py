from __future__ import annotations

import scripts.verify_pr009_quality as verifier


def test_pr009_verifier_unsupported_returns_two_without_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(verifier, "_unsupported", lambda: True)
    assert verifier.main() == 2
    assert capsys.readouterr().out == ""


def test_pr009_verifier_product_failure_returns_one(monkeypatch, capsys) -> None:
    monkeypatch.setattr(verifier, "_unsupported", lambda: False)
    monkeypatch.setattr(
        verifier,
        "run_supported",
        lambda: verifier.VerificationRun(
            {name: name == "schema_version" for name in verifier._CHECKS}
        ),
    )
    assert verifier.main() == 1
    out = capsys.readouterr().out
    assert "PR009_VERIFY schema_version=5" in out
    assert "PR009_VERIFY migration_v0005=FAIL" in out
    assert "PR009_VERIFY result=FAIL" in out


def test_pr009_renderer_success_output_is_exact() -> None:
    statuses = {name: True for name in verifier._CHECKS}
    assert verifier._render(statuses) == (
        "PR009_VERIFY schema_version=5",
        "PR009_VERIFY migration_v0005=PASS",
        "PR009_VERIFY import_decoder_compat=PASS",
        "PR009_VERIFY quality_decoder=PASS",
        "PR009_VERIFY metrics=PASS",
        "PR009_VERIFY persistence=PASS",
        "PR009_VERIFY audit=PASS",
        "PR009_VERIFY rollback=PASS",
        "PR009_VERIFY privacy=PASS",
        "PR009_VERIFY result=PASS",
    )


def test_pr009_decoder_and_metric_contract_uses_literal_vectors() -> None:
    decoder = verifier.PillowMediaDecoder()
    content = verifier._synthetic_png()
    assert verifier._assert_decoder_and_metrics(content, decoder)
