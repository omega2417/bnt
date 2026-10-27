"""Set-theoretic data model (Section 3).

  * identifier map iota(i, j, k) = c_i.Sj.Ak and its inverse (Proposition 1);
  * technique alphabet with an injective coding (Definition 2);
  * scenario projections, admissibility (3), order, join and meet (4)
    and the down-set encoding of Proposition 2;
  * Jaccard distance between projections (Section 3.3).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping

#: CREF tasks (objectives) in index order i = 1..8
TASKS = {1: ("PA", "Prevent/Avoid"), 2: ("PR", "Prepare"), 3: ("CN", "Continue"),
         4: ("CS", "Constrain"), 5: ("RE", "Reconstitute"), 6: ("UN", "Understand"),
         7: ("TR", "Transform"), 8: ("RA", "Re-Architect")}

#: CREF goals
GOALS = {"ANT": "Anticipate", "WITH": "Withstand", "REC": "Recover", "AD": "Adapt"}

#: the fourteen techniques of NIST SP 800-160 Vol. 2 with disambiguated codes
TECHNIQUES = {"AR": "Adaptive Response", "AM": "Analytic Monitoring",
              "CA": "Contextual Awareness", "CP": "Coordinated Protection",
              "DE": "Deception", "DV": "Diversity", "DP": "Dynamic Positioning",
              "NP": "Non-Persistence", "PR": "Privilege Restriction",
              "RD": "Redundancy", "RL": "Realignment", "S": "Segmentation",
              "SI": "Substantiated Integrity", "U": "Unpredictability"}

_CODE_RE = re.compile(r"^[A-Z]+$")
_ID_RE = re.compile(r"^([A-Z]+)\.S([1-9][0-9]*)\.A([1-9][0-9]*)$")
_TASK_BY_CODE = {c: i for i, (c, _) in TASKS.items()}


# --------------------------------------------------------------- identifiers
def check_code(code: str) -> list[str]:
    """Return problems with a task/technique code (empty list if valid).

    Detects non-Latin look-alike letters, e.g. a Cyrillic 'С' in 'СN'
    (one such entry was found in the source tabulation, Section 3.4).
    """
    problems = []
    for ch in code:
        if not ("A" <= ch <= "Z"):
            name = unicodedata.name(ch, "UNKNOWN")
            problems.append(f"character {ch!r} (U+{ord(ch):04X}, {name}) is not a Latin capital")
    if not code:
        problems.append("empty code")
    return problems


def iota(i: int, j: int, k: int, tasks: Mapping[int, tuple[str, str]] = TASKS) -> str:
    """Identifier map iota(i, j, k) = c_i.Sj.Ak (Definition 1)."""
    if min(i, j, k) < 1:
        raise ValueError("indices start at 1")
    return f"{tasks[i][0]}.S{j}.A{k}"


def iota_inv(identifier: str, tasks: Mapping[int, tuple[str, str]] = TASKS) -> tuple[int, int, int]:
    """Inverse of iota by parsing (Proposition 1)."""
    mt = _ID_RE.match(identifier)
    if not mt:
        bad = check_code(identifier.split(".")[0])
        raise ValueError(f"malformed identifier {identifier!r}" + (f": {bad}" if bad else ""))
    by_code = {c: i for i, (c, _) in tasks.items()}
    code, j, k = mt.group(1), int(mt.group(2)), int(mt.group(3))
    if code not in by_code:
        raise ValueError(f"unknown task code {code!r}")
    return by_code[code], j, k


def is_injective(mapping: Mapping) -> bool:
    """True if no two keys share a value."""
    vals = list(mapping.values())
    return len(vals) == len(set(vals))


# --------------------------------------------------------------- projections
@dataclass(frozen=True)
class Projection:
    """Projection P = (I_P, alpha_P) of the data model (Definition 3)."""

    alpha: Mapping[str, frozenset] = field(default_factory=dict)
    name: str = ""

    def __post_init__(self):
        object.__setattr__(self, "alpha",
                           {b: frozenset(a) for b, a in dict(self.alpha).items()})

    @property
    def actions(self) -> frozenset:
        return frozenset(self.alpha)

    def techniques(self, beta: str) -> frozenset:
        return self.alpha.get(beta, frozenset())

    # admissibility (3) -------------------------------------------------
    def violations(self, catalog: Mapping[str, Iterable[str]]) -> list[str]:
        out = []
        for b, a in self.alpha.items():
            if b not in catalog:
                out.append(f"{b}: not in the catalog index set")
            elif not a <= frozenset(catalog[b]):
                extra = sorted(a - frozenset(catalog[b]))
                out.append(f"{b}: techniques {extra} not in catalog set {sorted(catalog[b])}")
        return out

    def is_admissible(self, catalog: Mapping[str, Iterable[str]]) -> bool:
        return not self.violations(catalog)

    # order and lattice operations (4) ----------------------------------
    def __le__(self, other: "Projection") -> bool:
        return all(b in other.alpha and a <= other.alpha[b] for b, a in self.alpha.items())

    def __or__(self, other: "Projection") -> "Projection":   # join
        keys = self.actions | other.actions
        return Projection({b: self.techniques(b) | other.techniques(b) for b in keys},
                          name=f"({self.name} ⊔ {other.name})")

    def __and__(self, other: "Projection") -> "Projection":  # meet
        keys = self.actions & other.actions
        return Projection({b: self.techniques(b) & other.techniques(b) for b in keys},
                          name=f"({self.name} ⊓ {other.name})")

    def __eq__(self, other) -> bool:
        return isinstance(other, Projection) and dict(self.alpha) == dict(other.alpha)

    def __hash__(self):
        return hash(frozenset(self.alpha.items()))

    # down-set encoding (proof of Proposition 2) ------------------------
    def downset(self) -> frozenset:
        """E(P) = {(beta, *)} ∪ {(beta, a) : a in alpha_P(beta)}."""
        return frozenset([(b, "*") for b in self.alpha] +
                         [(b, a) for b, s in self.alpha.items() for a in s])


def poset_size(catalog: Mapping[str, Iterable[str]]) -> int:
    """|U| = |I| + sum |alpha(beta)| (Proposition 2)."""
    return len(catalog) + sum(len(set(a)) for a in catalog.values())


def jaccard_index(a: frozenset, b: frozenset) -> float:
    union = a | b
    return 1.0 if not union else len(a & b) / len(union)


def jaccard_distance(P: Projection, Q: Projection, on: str = "actions") -> float:
    """d_J on action sets (on='actions') or on down-sets (on='downset')."""
    if on == "actions":
        return 1.0 - jaccard_index(P.actions, Q.actions)
    if on == "downset":
        return 1.0 - jaccard_index(P.downset(), Q.downset())
    raise ValueError("on must be 'actions' or 'downset'")
