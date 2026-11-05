"""Linking of exchanges to activities and biosphere flows.

Matching is always case-insensitive and ignores leading/trailing whitespace (this is how Brightway's
``ExchangeLinker`` hashes fields). Optionally, the characters ``()[],'"`` can be removed before matching.

Unlike the previous function-based API, linking no longer modifies Brightway's global ``ExchangeLinker`` defaults.
"""

import collections
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import bw2data
import bw2io

from . import _helpers as hp

TECHNOSPHERE_KINDS: tuple[str, ...] = ("production", "substitution", "technosphere")
ACTIVITY_FIELDS: tuple[str, ...] = ("name", "unit", "location")
BIOSPHERE_FIELDS: tuple[str, ...] = ("name", "top_category", "sub_category", "location", "unit")
BIOSPHERE_TOP_CATEGORY_FIELDS: tuple[str, ...] = ("name", "top_category", "location", "unit")


def _exchange_linker(remove_special_characters: bool) -> type[bw2io.utils.ExchangeLinker]:
    """Return an ``ExchangeLinker`` subclass that does or does not strip special characters."""
    default_re_sub = bw2io.utils.ExchangeLinker.re_sub if remove_special_characters else None

    def parse_field(field_value, case_insensitive=True, strip=True, re_sub=default_re_sub):
        if field_value is None:
            return None
        value = str(field_value)
        if case_insensitive:
            value = value.lower()
        if strip:
            value = value.strip()
        if re_sub is not None:
            value = re_sub.sub("", value)
        return value

    return type("RosettaExchangeLinker", (bw2io.utils.ExchangeLinker,), {"parse_field": staticmethod(parse_field)})


def _kinds(production: bool, substitution: bool, technosphere: bool) -> tuple[str, ...]:
    return tuple(kind for kind, selected in zip(TECHNOSPHERE_KINDS, (production, substitution, technosphere)) if selected)


@dataclass(frozen=True)
class Linker:
    """Link exchanges of a list of datasets (strategy-style: every method takes and returns the data).

    Parameters
    ----------
    remove_special_characters
        Remove the characters ``()[],'"`` from field values before matching.
    """

    remove_special_characters: bool = False

    @property
    def _linker(self) -> type[bw2io.utils.ExchangeLinker]:
        return _exchange_linker(self.remove_special_characters)

    def link_internally(self,
                        data: list[dict],
                        production: bool = True,
                        substitution: bool = True,
                        technosphere: bool = True,
                        relink: bool = False,
                        fields: Sequence[str] = ACTIVITY_FIELDS) -> list[dict]:
        """Link production/substitution/technosphere exchanges to activities within ``data``."""
        return self._linker.link_iterable_by_fields(data,
                                                    fields=tuple(fields),
                                                    internal=True,
                                                    kind=_kinds(production, substitution, technosphere),
                                                    relink=relink)

    def link_externally(self,
                        data: list[dict],
                        databases: Sequence[str],
                        production: bool = True,
                        substitution: bool = True,
                        technosphere: bool = True,
                        relink: bool = False,
                        fields: Sequence[str] = ACTIVITY_FIELDS) -> list[dict]:
        """Link technosphere-type exchanges to activities of registered Brightway ``databases``.

        Databases are tried in the given order; the first match wins. With ``relink``, the order is reversed
        so that the first database still takes precedence when existing links are overwritten.
        """
        kinds = _kinds(production, substitution, technosphere)
        if not kinds:
            return data
        for db_name in (tuple(reversed(databases)) if relink else tuple(databases)):
            data = self._linker.link_iterable_by_fields(data,
                                                        other=(m for m in bw2data.Database(db_name)),
                                                        fields=tuple(fields),
                                                        internal=False,
                                                        kind=kinds,
                                                        relink=relink)
        return data

    def link_biosphere(self,
                       data: list[dict],
                       databases: Sequence[str],
                       relink: bool = False) -> list[dict]:
        """Link biosphere exchanges to flows of registered biosphere ``databases``.

        For each database, flows are first matched on name, top and sub category, location and unit, then flows
        that only have a top category are matched on name, top category, location and unit.
        """
        if relink:
            for ds in data:
                for exc in ds["exchanges"]:
                    if exc["type"] == "biosphere":
                        exc.pop("input", None)
        for db_name in (tuple(reversed(databases)) if relink else tuple(databases)):
            data = self._linker.link_iterable_by_fields(data,
                                                        other=(m for m in bw2data.Database(db_name)),
                                                        fields=BIOSPHERE_FIELDS,
                                                        internal=False,
                                                        kind={"biosphere"},
                                                        relink=relink)
            data = self._linker.link_iterable_by_fields(data,
                                                        other=(m for m in bw2data.Database(db_name) if len(m["categories"]) == 1),
                                                        fields=BIOSPHERE_TOP_CATEGORY_FIELDS,
                                                        internal=False,
                                                        kind={"biosphere"},
                                                        relink=relink)
        return data

    def link_to_iterable(self,
                         data: list[dict],
                         other: Iterable[dict],
                         fields: Sequence[str],
                         kinds: Iterable[str] | str | None = None,
                         relink: bool = False) -> list[dict]:
        """Link exchanges of the given ``kinds`` to any iterable of datasets that have 'database' and 'code'."""
        return self._linker.link_iterable_by_fields(data,
                                                    other=other,
                                                    fields=tuple(fields),
                                                    internal=False,
                                                    kind=kinds,
                                                    relink=relink)


def unlink(data: list[dict],
           production: bool = True,
           substitution: bool = True,
           technosphere: bool = True,
           biosphere: bool = True) -> list[dict]:
    """Remove 'input' and 'output' from exchanges of the selected types."""
    selected = {kind for kind, flag in (("production", production),
                                        ("substitution", substitution),
                                        ("technosphere", technosphere),
                                        ("biosphere", biosphere)) if flag}
    for ds in data:
        for exc in ds["exchanges"]:
            if exc["type"] in selected:
                exc.pop("input", None)
                exc.pop("output", None)
    return data


def unlinked_summary(data: list[dict]) -> dict[str, int]:
    """Number of unique unlinked exchanges per exchange type."""
    unique_unlinked = collections.defaultdict(set)
    for ds in data:
        for exc in (e for e in ds.get("exchanges", []) if not e.get("input")):
            fields = BIOSPHERE_FIELDS if exc["type"] == "biosphere" else ACTIVITY_FIELDS
            unique_unlinked[exc.get("type")].add(hp.format_values(tuple(exc[m] for m in fields),
                                                                  case_insensitive=True,
                                                                  strip=True,
                                                                  remove_special_characters=False))
    return {k: len(v) for k, v in unique_unlinked.items()}
