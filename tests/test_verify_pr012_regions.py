import scripts.verify_pr012_regions as verifier


def test_success_output_is_exact_and_safe(capsys) -> None:
    assert verifier.main() == 0
    output = capsys.readouterr().out.splitlines()
    assert output == list(verifier._LABELS)
    forbidden = ("SELECT ", "INSERT ", "/tmp/", "00000000-", "key=", "x=")
    assert not any(value in "\n".join(output) for value in forbidden)


def test_failure_is_sanitized(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        verifier,
        "_apply_migrations",
        lambda connection: (_ for _ in ()).throw(RuntimeError("private")),
    )
    assert verifier.main() == 1
    assert capsys.readouterr().out == "result=FAIL\n"
