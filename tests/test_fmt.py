from devin_search.fmt import (
    fmt_ts,
    hits_table,
    hits_to_dicts,
    stats_line,
    stats_to_dict,
)
from devin_search.index import IndexStats
from devin_search.query import Hit


def _hit(**kw):
    base = dict(
        session_id="abcdef01-2345-6789-abcd-ef0123456789",
        role="user",
        ts=1_780_000_000_000,
        project="/projects/alpha",
        session_title="alpha",
        source="sessions",
        ref="node:7",
        snippet="deploy with «kubectl»",
        rank=-1.5,
    )
    base.update(kw)
    return Hit(**base)


def test_hits_table_columns():
    table = hits_table([_hit()])
    lines = table.splitlines()
    assert "WHEN" in lines[0] and "SNIPPET" in lines[0]
    assert "user" in table and "alpha" in table
    assert "abcdef01" in table
    assert "«kubectl»" in table


def test_hits_table_empty():
    assert hits_table([]) == "no hits"


def test_hits_to_dicts_shape():
    (d,) = hits_to_dicts([_hit()])
    assert set(d) == {
        "session_id", "role", "ts", "project", "session_title",
        "source", "ref", "snippet", "rank",
    }
    assert d["ref"] == "node:7"
    assert d["rank"] == -1.5


def test_fmt_ts():
    assert fmt_ts(0) == "-"
    assert fmt_ts(1_780_000_000_000) == "2026-05-28 20:26"


def test_stats_line_and_dict():
    stats = IndexStats(
        index_path="/tmp/search.db",
        message_nodes=3,
        prompt_history=1,
        tool_calls=2,
        acp_messages=4,
        removed=1,
        sources=["sessions", "acp"],
    )
    line = stats_line(stats)
    assert "+10 docs" in line and "removed 1" in line
    d = stats_to_dict(stats)
    assert d["indexed"] == 10
    assert d["by_source"]["acp_messages"] == 4
    assert d["sources"] == ["sessions", "acp"]
