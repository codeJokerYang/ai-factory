"""DAG 校验：依赖完整性 + 循环依赖检测（ARCHITECTURE FR-1.6 / §6.1.2 Reviewer 检查项）。"""
from __future__ import annotations

from .schemas import Dag


class DagValidationError(ValueError):
    pass


def validate_dag(dag: Dag) -> None:
    """不合法时抛 DagValidationError。"""
    ids = [n.id for n in dag.nodes]
    if not ids:
        raise DagValidationError("DAG 没有任何节点")
    if len(ids) != len(set(ids)):
        raise DagValidationError("存在重复的节点 id")

    idset = set(ids)
    for node in dag.nodes:
        for dep in node.depends:
            if dep not in idset:
                raise DagValidationError(f"节点 {node.id} 依赖了不存在的 id: {dep}")

    _check_cycles(dag)


def _check_cycles(dag: Dag) -> None:
    graph = {n.id: list(n.depends) for n in dag.nodes}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in graph}

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in graph[u]:
            if color[v] == GRAY:
                raise DagValidationError(f"检测到循环依赖: {u} -> {v}")
            if color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    for nid in graph:
        if color[nid] == WHITE:
            dfs(nid)
