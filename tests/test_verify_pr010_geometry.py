from scripts.verify_pr010_geometry import main


def test_verify_pr010_geometry():
    assert main() == 0
