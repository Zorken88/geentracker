"""Tests de la línea base energética y EnPI (ISO 50001)."""

from greentracker.baseline import BaselineManager
from greentracker.csv_writer import CsvWriter

from test_csv_writer import make_summary


def test_first_session_is_baseline(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    manager = BaselineManager(csv_file)
    assert manager.is_first_session("demo") is True
    CsvWriter(csv_file).write_session_summary(make_summary(is_baseline=True))
    assert manager.is_first_session("demo") is False
    base = manager.get_baseline("demo")
    assert base is not None
    assert base["session_id"] == "abc123"


def test_baseline_is_per_project(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    CsvWriter(csv_file).write_session_summary(make_summary(project="api"))
    manager = BaselineManager(csv_file)
    assert manager.is_first_session("api") is False
    assert manager.is_first_session("otro-proyecto") is True
    assert manager.get_baseline("otro-proyecto") is None


def test_compare_to_baseline_deltas(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.write_session_summary(make_summary(session_id="base", energy=0.010))
    manager = BaselineManager(csv_file)
    # sesión nueva con la mitad de energía → -50%
    result = manager.compare_to_baseline("demo", energy_kwh=0.005, emissions_kg=0.005 * 0.245)
    assert result is not None
    assert result["baseline_session_id"] == "base"
    assert abs(result["energy_delta_pct"] - (-50.0)) < 1e-6
    assert abs(result["emissions_delta_pct"] - (-50.0)) < 1e-6


def test_set_baseline_rewrites_flags(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.write_session_summary(make_summary(session_id="s1", is_baseline=True))
    writer.write_session_summary(make_summary(session_id="s2", is_baseline=False))
    manager = BaselineManager(csv_file)
    assert manager.set_baseline("demo", "s2") is True
    base = manager.get_baseline("demo")
    assert base["session_id"] == "s2"
    # la anterior dejó de ser línea base
    rows = manager.sessions("demo")
    flags = {r["session_id"]: r["is_baseline"] for r in rows}
    assert flags == {"s1": "False", "s2": "True"}


def test_set_baseline_unknown_session(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    CsvWriter(csv_file).write_session_summary(make_summary(session_id="s1"))
    assert BaselineManager(csv_file).set_baseline("demo", "no-existe") is False
