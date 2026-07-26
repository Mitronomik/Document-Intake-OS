from scripts import verify_pr011_jpeg as verifier


def test_unsupported_is_exact(monkeypatch, capsys):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Linux")
    assert verifier.main() == 2
    assert capsys.readouterr().out == "PR011_VERIFY result=INCONCLUSIVE\n"


def test_windows_success_is_allowlisted(monkeypatch, capsys):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Windows")
    assert verifier.main() == 0
    assert tuple(capsys.readouterr().out.splitlines()) == verifier._SUCCESS
