import pandas as pd
import pytest

from tests.sample_lists import day_one, day_two, to_csv
from tracker.uksl import diff, read_raw, to_designations
from tracker.update import run


def test_parser_skips_title_row_and_groups_names():
    designations = to_designations(read_raw(to_csv(day_one())))
    assert len(designations) == 6
    petrov = designations.set_index("unique_id").loc["RUS0001"]
    assert petrov["primary_name"] == "Ivan PETROV"
    assert petrov["other_names"] == "PETROFF"
    assert petrov["sanctions_imposed"] == "Asset freeze; Travel ban"


def test_diff_finds_added_removed_and_amended():
    before = to_designations(read_raw(to_csv(day_one())))
    after = to_designations(read_raw(to_csv(day_two())))
    changes = diff(before, after, "2026-10-02").set_index("unique_id")

    assert set(changes.index[changes.change_type == "Added"]) == {"CYB0001", "CYB0002"}
    assert set(changes.index[changes.change_type == "Removed"]) == {"GHR0001"}
    assert set(changes.index[changes.change_type == "Amended"]) == {"RUS0001", "RUS0002"}
    assert "Sanctions imposed" in changes.loc["RUS0002", "fields_changed"]
    assert "Aliases" in changes.loc["RUS0001", "fields_changed"]


def test_unchanged_list_gives_no_changes():
    d = to_designations(read_raw(to_csv(day_one())))
    assert diff(d, d, "2026-10-02").empty


def test_run_builds_history(tmp_path):
    first = run(to_csv(day_one()), "2026-10-01", tmp_path)
    assert first["baseline"] and first["total_designations"] == 6

    second = run(to_csv(day_two()), "2026-10-02", tmp_path)
    assert (second["added"], second["removed"], second["amended"]) == (2, 1, 2)

    runs = pd.read_csv(tmp_path / "runs.csv")
    assert list(runs["run_date"]) == ["2026-10-01", "2026-10-02"]
    assert len(pd.read_csv(tmp_path / "changes.csv")) == 5


def test_bad_download_is_rejected(tmp_path):
    run(to_csv(day_one()), "2026-10-01", tmp_path)
    with pytest.raises(ValueError):
        run(to_csv(day_one()[:2]), "2026-10-02", tmp_path)
    assert len(pd.read_csv(tmp_path / "runs.csv")) == 1
