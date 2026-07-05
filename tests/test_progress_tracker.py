import pytest

from app.agents import progress_tracker


@pytest.fixture(autouse=True)
def clear_mastery_log():
    """Each test starts from a clean tracker — it's a module-level singleton."""
    progress_tracker._mastery_log.clear()
    yield
    progress_tracker._mastery_log.clear()


def test_record_progress_stores_step_mastery():
    result = progress_tracker.record_progress("Step 1: Basics", mastered=True)
    assert result == {"step": "Step 1: Basics", "mastered": True}


def test_get_mastery_summary_empty():
    summary = progress_tracker.get_mastery_summary()
    assert summary == {
        "total_steps": 0,
        "mastered_steps": 0,
        "mastery_rate": 0.0,
        "detail": {},
    }


def test_get_mastery_summary_with_mixed_results():
    progress_tracker.record_progress("Step 1", mastered=True)
    progress_tracker.record_progress("Step 2", mastered=False)
    progress_tracker.record_progress("Step 3", mastered=True)

    summary = progress_tracker.get_mastery_summary()

    assert summary["total_steps"] == 3
    assert summary["mastered_steps"] == 2
    assert summary["mastery_rate"] == pytest.approx(2 / 3)
    assert summary["detail"] == {"Step 1": True, "Step 2": False, "Step 3": True}


def test_record_progress_overwrites_same_step():
    progress_tracker.record_progress("Step 1", mastered=False)
    progress_tracker.record_progress("Step 1", mastered=True)

    summary = progress_tracker.get_mastery_summary()

    assert summary["total_steps"] == 1
    assert summary["detail"]["Step 1"] is True
