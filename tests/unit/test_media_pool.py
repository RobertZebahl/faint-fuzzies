"""The order media_pool._dss_run tries DSS sources in: every source by name before any by coordinates. The fetch
functions are stubbed, so no network is ever reached."""
from faint_fuzzies.domain import dss
from faint_fuzzies.media_pool import _dss_run

_SOURCES = (dss.DSSSource.DSS1, dss.DSSSource.DSS2_RED)


def _dss_fetch(tmp_path, monkeypatch, by_name, succeed_at=None):
    """Runs one DSSTask (DSS1, then DSS2_RED) through _dss_run with both fetch functions recording every attempt as
    ("name"/"coordinates", source) and succeeding only for `succeed_at`; returns the attempts and the result."""
    calls = []

    def stub(kind):
        def run(_target, source, _fov, _destination):
            attempt = (kind, source.value)
            calls.append(attempt)
            return attempt == succeed_at
        return run

    monkeypatch.setattr(dss, "fetch_dss_image_by_name", stub("name"))
    monkeypatch.setattr(dss, "fetch_dss_image_by_coordinates", stub("coordinates"))
    task = dss.DSSTask(catalogue="own", label="M13", by_name=by_name, coordinates=(1.0, 2.0), position="x",
                       sources=_SOURCES, fov=5.0)
    succeeded = _dss_run(task, tmp_path)()
    return calls, succeeded


def test_every_source_is_tried_by_name_before_any_by_coordinates(tmp_path, monkeypatch):
    calls, succeeded = _dss_fetch(tmp_path, monkeypatch, by_name=True)
    assert calls == [("name", "dss1"), ("name", "dss2red"), ("coordinates", "dss1"), ("coordinates", "dss2red")]
    assert succeeded is False


def test_a_task_not_marked_by_name_skips_straight_to_coordinates(tmp_path, monkeypatch):
    calls, _ = _dss_fetch(tmp_path, monkeypatch, by_name=False)
    assert calls == [("coordinates", "dss1"), ("coordinates", "dss2red")]


def test_the_fetch_stops_at_the_first_success_by_name(tmp_path, monkeypatch):
    """A less-preferred by-name source succeeding still wins over ever trying coordinates."""
    calls, succeeded = _dss_fetch(tmp_path, monkeypatch, by_name=True, succeed_at=("name", "dss2red"))
    assert calls == [("name", "dss1"), ("name", "dss2red")]
    assert succeeded is True


def test_coordinates_are_only_tried_after_every_name_attempt_fails(tmp_path, monkeypatch):
    calls, succeeded = _dss_fetch(tmp_path, monkeypatch, by_name=True, succeed_at=("coordinates", "dss1"))
    assert calls == [("name", "dss1"), ("name", "dss2red"), ("coordinates", "dss1")]
    assert succeeded is True
