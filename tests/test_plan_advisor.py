from __future__ import annotations

from sparkstagelapse.dashboard.rendering.plan_advisor import analyze_plan
from sparkstagelapse.dashboard.rendering.plan_html import parse_physical_plan, plan_to_html

SORT_MERGE_PLAN = """== Physical Plan ==
*(5) SortMergeJoin [id#1], [id#2], Inner
:- *(2) Sort [id#1 ASC NULLS FIRST], false, 0
:  +- Exchange hashpartitioning(id#1, 200), ENSURE_REQUIREMENTS, [id=#45]
:     +- *(1) FileScan parquet default.a[id#1] Batched: true, DataFilters: [], Format: Parquet, Location: InMemoryFileIndex(1 paths)[file:/a], PartitionFilters: [], PushedFilters: [], ReadSchema: struct<id:int>
+- *(4) Sort [id#2 ASC NULLS FIRST], false, 0
   +- Exchange hashpartitioning(id#2, 200), ENSURE_REQUIREMENTS, [id=#52]
      +- *(3) FileScan parquet default.b[id#2] Batched: true, DataFilters: [], Format: Parquet, Location: InMemoryFileIndex(1 paths)[file:/b], PartitionFilters: [], PushedFilters: [], ReadSchema: struct<id:int>
"""

CARTESIAN_PLAN = """== Physical Plan ==
CartesianProduct
:- FileScan parquet default.a[id#1] Batched: true, DataFilters: [], Format: Parquet, Location: InMemoryFileIndex(1 paths)[file:/a], PartitionFilters: [], PushedFilters: [], ReadSchema: struct<id:int>
+- FileScan parquet default.b[id#2] Batched: true, DataFilters: [], Format: Parquet, Location: InMemoryFileIndex(1 paths)[file:/b], PartitionFilters: [], PushedFilters: [], ReadSchema: struct<id:int>
"""

CLEAN_PLAN = """== Physical Plan ==
*(1) FileScan parquet default.a[id#1] Batched: true, DataFilters: [isnotnull(id#1)], Format: Parquet, Location: InMemoryFileIndex(1 paths)[file:/a], PartitionFilters: [], PushedFilters: [IsNotNull(id)], ReadSchema: struct<id:int>
"""


def test_sort_merge_join_suggests_broadcast():
    nodes = parse_physical_plan(SORT_MERGE_PLAN)
    levels_and_messages = [(s["level"], s["message"]) for s in analyze_plan(nodes)]
    assert any("broadcast" in msg.lower() for _, msg in levels_and_messages)


def test_cartesian_product_warns():
    nodes = parse_physical_plan(CARTESIAN_PLAN)
    suggestions = analyze_plan(nodes)
    assert any(s["level"] == "warn" and "cartesian" in s["message"].lower() for s in suggestions)


def test_clean_plan_has_no_suggestions():
    nodes = parse_physical_plan(CLEAN_PLAN)
    assert analyze_plan(nodes) == []


def test_plan_to_html_embeds_suggestions_panel():
    html = plan_to_html(SORT_MERGE_PLAN, "t", "plan_1")
    assert 'data-role="plan-suggestions"' in html
    assert "broadcast" in html.lower()


def test_plan_to_html_omits_panel_when_no_suggestions():
    html = plan_to_html(CLEAN_PLAN, "t", "plan_2")
    assert 'data-role="plan-suggestions"' not in html
