"""The 27 implementation checks of Section 4.6, one pytest case each."""
import pytest

from recovery_evidence.checks import CHECKS, run_checks


def test_there_are_27_checks():
    assert len(CHECKS) == 27


@pytest.mark.parametrize("title,fn", CHECKS, ids=[f"check{i:02d}" for i in range(1, len(CHECKS) + 1)])
def test_control_check(title, fn):
    assert isinstance(fn(), str)


def test_report_text():
    results, text = run_checks()
    assert all(ok for _, ok, _ in results)
    assert text.rstrip().endswith("27 of 27 checks passed.")
