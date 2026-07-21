from __future__ import annotations


def test_pr009_verifier_success_output(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from scripts import verify_pr009_quality as verifier

    monkeypatch.setattr(verifier, "_sqlcipher_supported", lambda: True)
    assert verifier.main() == 0
    lines = tuple(capsys.readouterr().out.splitlines())
    assert lines == verifier._SUCCESS_LINES


def test_pr009_verifier_product_failure_returns_one(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from scripts import verify_pr009_quality as verifier

    monkeypatch.setattr(verifier, "_sqlcipher_supported", lambda: True)
    statuses = dict.fromkeys(verifier._CHECKS, True)
    statuses["quality_decoder"] = False
    monkeypatch.setattr(verifier, "_run_supported", lambda: verifier._Run(statuses))
    assert verifier.main() == 1
    out = capsys.readouterr().out
    assert "PR009_VERIFY quality_decoder=FAIL" in out
    assert "PR009_VERIFY result=FAIL" in out


def test_pr009_verifier_unsupported_returns_two_without_pass(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from scripts import verify_pr009_quality as verifier

    monkeypatch.setattr(verifier, "_sqlcipher_supported", lambda: False)
    assert verifier.main() == 2
    assert capsys.readouterr().out == ""
