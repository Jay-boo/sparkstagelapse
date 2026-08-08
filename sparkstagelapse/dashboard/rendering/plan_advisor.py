from __future__ import annotations


def _has_op(nodes: list[dict], *names: str) -> bool:
    return any(any(name in node["op"] for name in names) for node in nodes)


def analyze_plan(nodes: list[dict]) -> list[dict]:
    """Runs rule-based heuristics over a `parse_physical_plan()` node list
    and returns a list of `{level, message}` suggestions ("warn" or "info",
    driving the badge color in the rendered panel).

    These are plan-shape heuristics only — they see operator names and
    detail strings, not row counts or data skew, so they catch generic
    anti-patterns (unnecessary shuffles, cartesian joins, non-pushed
    filters) but can't reason about actual runtime cost.
    """
    suggestions: list[dict] = []

    exchanges = [n for n in nodes if n["category"] == "exchange"]
    if len(exchanges) >= 3:
        suggestions.append({
            "level": "warn",
            "message": f"{len(exchanges)} shuffles detected — check if repartition/groupBy/join "
                       "keys can be aligned so the same data isn't re-shuffled multiple times.",
        })

    if any("SinglePartition" in n["detail"] for n in exchanges):
        suggestions.append({
            "level": "warn",
            "message": "A shuffle collapses data into a single partition (SinglePartition) — "
                       "common with orderBy/limit without partitioning, and a likely bottleneck "
                       "on large data.",
        })

    if _has_op(nodes, "SortMergeJoin"):
        suggestions.append({
            "level": "info",
            "message": "SortMergeJoin in use — if one side of the join is small, consider "
                       "broadcast() or raising spark.sql.autoBroadcastJoinThreshold to skip "
                       "the shuffle.",
        })

    if _has_op(nodes, "CartesianProduct", "BroadcastNestedLoopJoin"):
        suggestions.append({
            "level": "warn",
            "message": "Cartesian/nested-loop join detected — usually a missing or non-equi "
                       "join condition; verify the join key(s).",
        })

    has_filter = _has_op(nodes, "Filter")
    for n in nodes:
        if n["category"] == "scan" and "PushedFilters: []" in n["detail"] and has_filter:
            suggestions.append({
                "level": "info",
                "message": "A Filter isn't being pushed down to the scan (PushedFilters: []) — "
                           "check the filter expression and data source support for predicate "
                           "pushdown.",
            })
            break

    return suggestions
