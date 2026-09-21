"""Evaluation-only bookkeeping prototype. The skill does not invoke this module.

The caller owns materiality, authority, predicate evaluation, and whether affected
answers remain valid. Dirty descendants require reassessment, not automatic reversal.
"""
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: str
    status: str = 'unresolved'
    prerequisites: tuple = ()
    active: bool | None = True
    recommendation: str | None = None
    answer: str | None = None
    authority: str | None = None
    defer_reason: str | None = None
    revisit: str | None = None


class Ledger:
    def __init__(self):
        self._nodes = {}
        self._dirty = set()
        self.revision = 0
        self.confirmed = None

    @property
    def nodes(self):
        return deepcopy(self._nodes)

    @property
    def dirty(self):
        return frozenset(self._dirty)

    @staticmethod
    def validate(nodes):
        visited, visiting = set(), set()

        def visit(key):
            if key in visiting:
                raise ValueError('cycle')
            if key in visited:
                return
            if key not in nodes:
                raise ValueError('unknown_prerequisite')
            visiting.add(key)
            for parent in nodes[key].prerequisites:
                visit(parent)
            visiting.remove(key)
            visited.add(key)

        for key, node in nodes.items():
            if not isinstance(key, str) or not key or node.status not in {'unresolved', 'settled', 'deferred', 'superseded'}:
                raise ValueError('invalid_node')
            if not isinstance(node.prerequisites, tuple) or any(not isinstance(x, str) for x in node.prerequisites):
                raise ValueError('invalid_prerequisites')
            if node.active is not None and type(node.active) is not bool:
                raise ValueError('invalid_predicate')
            if node.status == 'settled' and (node.answer is None or not node.authority):
                raise ValueError('missing_answer_authority')
            if node.status == 'deferred' and (not node.defer_reason or not node.revisit):
                raise ValueError('missing_deferral_basis')
            visit(key)

    def affected(self, key):
        result, pending = set(), [key]
        while pending:
            parent = pending.pop()
            for candidate, node in self._nodes.items():
                if parent in node.prerequisites and candidate not in result:
                    result.add(candidate)
                    pending.append(candidate)
        return frozenset(result)

    def put(self, node):
        """Caller submits an interpreted change; reject bad graphs atomically."""
        if self._nodes.get(node.id) == node:
            return frozenset()
        proposed = {**self._nodes, node.id: node}
        self.validate(proposed)
        impacted = self.affected(node.id) if node.id in self._nodes else frozenset()
        self._nodes = proposed
        self._dirty.update(impacted)
        self.revision += 1
        self.confirmed = None
        return impacted

    def reassess(self, key, node):
        """Explicit host judgment that a dirty node is still valid or is revised."""
        if key != node.id or key not in self._nodes:
            raise ValueError('unknown_node')
        self.put(node)
        self._dirty.discard(key)

    def blockers(self):
        return frozenset(self._dirty | {key for key, n in self._nodes.items()
            if n.status == 'unresolved' or n.active is None or
            (n.active is False and n.status != 'superseded') or
            (n.status == 'settled' and any(self._nodes[p].status != 'settled'
                                         or self._nodes[p].active is not True or p in self._dirty for p in n.prerequisites))})

    def ready(self):
        return frozenset(key for key, n in self._nodes.items()
            if n.status == 'unresolved' and n.active is True and key not in self._dirty
            and all(self._nodes[p].status == 'settled' and self._nodes[p].active is True and p not in self._dirty
                    for p in n.prerequisites))

    def confirm(self, displayed_revision):
        if self.blockers() or displayed_revision != self.revision:
            raise ValueError('incomplete_or_stale_revision')
        self.confirmed = self.revision
