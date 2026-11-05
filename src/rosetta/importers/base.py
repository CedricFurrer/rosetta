"""Base importer with the processing steps shared by all rosetta LCI importers."""

import copy
import pathlib
import uuid
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from typing import Self

import bw2data
import bw2io

from .. import _helpers as hp
from ..linking import ACTIVITY_FIELDS, BIOSPHERE_FIELDS, Linker, unlink, unlinked_summary
from ..migration import Migration
from ..strategies.common import (change_database_name,
                                 select_inventory_using_regex,
                                 unregionalize_biosphere)


class LCIImporter(bw2io.importers.base_lci.LCIImporter):
    """Brightway LCI importer with rosetta's linking, migration and selection steps.

    All processing methods modify the importer in place and return it, so they can be chained::

        db.migrate("custom_migration.xlsx").link_biosphere().link_internally()

    Parameters
    ----------
    db_name
        Name of the database to write.
    data
        List of activity datasets.
    biosphere
        Name of the biosphere database that biosphere exchanges are linked to.
    unlinked_biosphere
        Name of the database that collects biosphere flows which could not be linked to ``biosphere``.
    linker
        Linker to use; defaults to ``Linker()`` (no removal of special characters).
    """

    def __init__(self,
                 db_name: str,
                 data: list[dict] | None = None,
                 biosphere: str | None = None,
                 unlinked_biosphere: str | None = None,
                 linker: Linker | None = None,
                 verbose: bool = True) -> None:
        super().__init__(db_name)
        # Per-instance metadata (Brightway's importer shares one class-level dict between all instances)
        self.metadata: dict = {}
        self.strategies: list[Callable] = []
        self.data: list[dict] = [] if data is None else data
        self.biosphere: str | None = biosphere
        self.unlinked_biosphere: str | None = unlinked_biosphere
        self.linker: Linker = Linker() if linker is None else linker
        self.verbose: bool = verbose

    def __repr__(self) -> str:
        return "{}(db_name={!r}, datasets={})".format(type(self).__name__, self.db_name, len(self.data))

    def __len__(self) -> int:
        return len(self.data)

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_brightway(cls, db_name: str, new_name: str | None = None, **kwargs) -> Self:
        """Load a registered Brightway database (activities with their exchanges) into a new importer."""
        if db_name not in bw2data.databases:
            raise ValueError("Database '{}' is not registered in the Brightway background and can therefore not be copied. Available databases are:\n{}".format(db_name, bw2data.databases))
        data: list[dict] = [{**act.as_dict(), "exchanges": [exc.as_dict() for exc in act.exchanges()]} for act in bw2data.Database(db_name)]
        importer = cls(db_name, data=copy.deepcopy(data), **kwargs)
        if new_name is not None and new_name != db_name:
            importer.rename(new_name)
        return importer

    def copy(self, db_name: str | None = None) -> Self:
        """Deep copy of this importer, optionally renamed to ``db_name``."""
        new = copy.deepcopy(self)
        if db_name is not None and db_name != self.db_name:
            new.rename(db_name)
        return new

    # ------------------------------------------------------------------ generic

    def apply(self, strategy: Callable[[list[dict]], list[dict]], **kwargs) -> Self:
        """Apply any strategy function (``data -> data``), passing ``kwargs`` to it."""
        self.apply_strategy(partial(strategy, **kwargs) if kwargs else strategy, verbose=self.verbose)
        return self

    def extend(self, other: "LCIImporter | Iterable[dict]") -> Self:
        """Append the datasets of another importer (or a list of datasets) to this importer.

        The datasets keep their database name; call :meth:`rename` afterwards to assign them to this database.
        """
        self.data += list(other.data if isinstance(other, bw2io.importers.base.ImportBase) else other)
        return self

    def select(self,
               patterns: Sequence[str],
               exclude: bool = False,
               db_name: str | None = None) -> "LCIImporter":
        """Return a new importer with (a deep copy of) the activities whose SimaPro name matches one of the regex ``patterns``.

        Matching is case-insensitive. With ``exclude=True``, the matching activities are left out instead.
        """
        data = select_inventory_using_regex(db_var=copy.deepcopy(self.data),
                                            exclude=exclude,
                                            include=not exclude,
                                            patterns=list(patterns),
                                            case_sensitive=True)
        new = LCIImporter(self.db_name,
                          data=data,
                          biosphere=self.biosphere,
                          unlinked_biosphere=self.unlinked_biosphere,
                          linker=self.linker,
                          verbose=self.verbose)
        if db_name is not None:
            new.rename(db_name)
        return new

    def rename(self, db_name: str) -> Self:
        """Rename the database and update links that pointed to the old name."""
        self.apply(change_database_name, new_db_name=db_name)
        self.db_name = db_name
        return self

    # ------------------------------------------------------------------ migration

    def migrate(self,
                migration: Migration | pathlib.Path | str,
                activities: bool = False,
                exchanges: bool = True) -> Self:
        """Apply a :class:`~rosetta.migration.Migration` (or an Excel/JSON migration file)."""
        if not isinstance(migration, Migration):
            migration = Migration.from_file(migration)
        return self.apply(migration.apply, activities=activities, exchanges=exchanges)

    # ------------------------------------------------------------------ linking

    def link_internally(self,
                        production: bool = True,
                        substitution: bool = True,
                        technosphere: bool = True,
                        relink: bool = False) -> Self:
        """Link exchanges to activities within this database (on name, unit and location)."""
        return self.apply(self.linker.link_internally,
                          production=production,
                          substitution=substitution,
                          technosphere=technosphere,
                          relink=relink)

    def link_to(self,
                *databases: str,
                production: bool = True,
                substitution: bool = True,
                technosphere: bool = True,
                relink: bool = False,
                fields: Sequence[str] = ACTIVITY_FIELDS) -> Self:
        """Link exchanges to activities in registered ``databases`` (first match wins)."""
        return self.apply(self.linker.link_externally,
                          databases=databases,
                          production=production,
                          substitution=substitution,
                          technosphere=technosphere,
                          relink=relink,
                          fields=fields)

    def link_biosphere(self, *databases: str, relink: bool = False) -> Self:
        """Link biosphere exchanges to registered biosphere databases.

        Defaults to ``self.biosphere`` followed by ``self.unlinked_biosphere`` (if set).
        """
        if not databases:
            databases = tuple(m for m in (self.biosphere, self.unlinked_biosphere) if m is not None)
        if not databases:
            raise ValueError("No biosphere database given. Pass database names or set 'biosphere' on the importer.")
        return self.apply(self.linker.link_biosphere, databases=databases, relink=relink)

    def unlink(self,
               production: bool = True,
               substitution: bool = True,
               technosphere: bool = True,
               biosphere: bool = True) -> Self:
        """Remove existing links ('input'/'output') from the selected exchange types."""
        return self.apply(unlink,
                          production=production,
                          substitution=substitution,
                          technosphere=technosphere,
                          biosphere=biosphere)

    def unlinked_summary(self) -> dict[str, int]:
        """Number of unique unlinked exchanges per exchange type."""
        return unlinked_summary(self.data)

    # ------------------------------------------------------------------ biosphere

    def unregionalize_biosphere(self) -> Self:
        """Set the location of all biosphere exchanges to 'GLO'."""
        return self.apply(unregionalize_biosphere)

    def add_unlinked_to_biosphere(self,
                                  unlinked_biosphere: str | None = None,
                                  biosphere: str | None = None) -> Self:
        """Register unlinked biosphere flows in the database ``unlinked_biosphere`` and link them.

        ``biosphere`` (an existing, non-empty biosphere) determines which fields the new flows keep.
        Defaults to ``self.unlinked_biosphere`` and ``self.biosphere``.
        """
        unlinked_name: str | None = unlinked_biosphere or self.unlinked_biosphere
        biosphere_name: str | None = biosphere or self.biosphere
        if unlinked_name is None or biosphere_name is None:
            raise ValueError("Both 'unlinked_biosphere' and 'biosphere' need to be given or set on the importer.")

        if unlinked_name not in bw2data.databases:
            bw2data.Database(unlinked_name).register()

        def identifier(flow) -> tuple:
            return hp.format_values(tuple([flow[m] for m in BIOSPHERE_FIELDS]),
                                    case_insensitive=True,
                                    strip=True,
                                    remove_special_characters=False)

        existing: list[tuple] = [identifier(v) for v in copy.deepcopy(bw2data.Database(unlinked_name))]

        # Unique unlinked biosphere exchanges that are not yet in the unlinked biosphere database
        unlinked_flows: dict = {identifier(exc): exc for ds in self.data for exc in ds["exchanges"]
                                if exc["type"] == "biosphere" and not exc.get("input")}
        unlinked_flows = {k: v for k, v in unlinked_flows.items() if k not in existing}

        if len(list(bw2data.Database(biosphere_name))) == 0:
            raise ValueError("Biosphere database '" + str(biosphere_name) + "' not existing or empty")

        # Only keep the fields that flows of the biosphere database have
        keep_keys = list(bw2data.Database(biosphere_name).random().as_dict().keys())
        new_flows: list[dict] = [dict({k: v for k, v in exc.items() if k in keep_keys},
                                      **{"code": str(uuid.uuid4()),
                                         "type": "natural resource" if exc["categories"][0].lower() in ["raw", "natural resource"] else "emission",
                                         "exchanges": []}) for exc in unlinked_flows.values()]

        if len(new_flows) == 0:
            return self

        # Rewrite the unlinked biosphere database with the existing and the new flows
        db_unlinked = LCIImporter.from_brightway(unlinked_name) if unlinked_name in bw2data.databases else LCIImporter(unlinked_name)
        db_unlinked.verbose = False
        db_unlinked.data += [{**m, "database": unlinked_name} for m in new_flows]
        if unlinked_name in bw2data.databases:
            del bw2data.databases[unlinked_name]
        db_unlinked.write_database()

        if self.verbose:
            print("\n------ Unlinked biosphere database update")
            print("Registered {} new unique biosphere flows to '{}'".format(len(new_flows), unlinked_name))

        return self.apply(self.linker.link_to_iterable,
                          other=(m for m in bw2data.Database(unlinked_name)),
                          fields=BIOSPHERE_FIELDS,
                          kinds={"biosphere"},
                          relink=False)

    # ------------------------------------------------------------------ writing

    def write(self, overwrite: bool = False, **kwargs) -> bw2data.Database:
        """Write the database to Brightway. With ``overwrite``, an existing database of the same name is deleted first."""
        if self.db_name in bw2data.databases:
            if not overwrite:
                raise ValueError("Database '{}' already exists. Use 'overwrite=True' to replace it.".format(self.db_name))
            if self.verbose:
                print("\n------- Delete database: " + self.db_name)
            del bw2data.databases[self.db_name]
        if self.verbose:
            print("\n------- Write database: " + self.db_name)
        return self.write_database(**kwargs)
