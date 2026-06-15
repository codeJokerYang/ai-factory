"""DAG 校验：依赖完整性 + 循环依赖检测（ARCHITECTURE FR-1.6 / §6.1.2 Reviewer 检查项）。"""
from __future__ import annotations

from typing import Optional

from . import config
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


def check_granularity(dag: Dag, lo: Optional[int] = None, hi: Optional[int] = None) -> Optional[str]:
    """粒度软校验：节点数越界返回非阻塞 warning 文案，区间内返回 None。"""
    lo = config.DAG_MIN_NODES if lo is None else lo
    hi = config.DAG_MAX_NODES if hi is None else hi
    n = len(dag.nodes)
    if n < lo:
        return f"DAG 仅 {n} 个节点，低于建议下限 {lo}（可能拆得过粗）"
    if n > hi:
        return f"DAG 有 {n} 个节点，高于建议上限 {hi}（可能拆得过细）"
    return None
