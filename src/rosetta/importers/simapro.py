"""Importers for SimaPro CSV exports (inventories and LCIA methods)."""

import copy
import pathlib
import uuid
from collections.abc import Iterable
from functools import partial

import bw2data
import bw2io

from .. import _helpers as hp
from ..linking import Linker
from ..methods import append_missing_regionalized_flows_to_methods
from ..strategies.common import (add_code_field,
                                 add_location_to_biosphere_exchanges,
                                 add_top_and_subcategory_fields_for_biosphere_flows,
                                 add_top_category_factors_as_proxy_for_sub_categories,
                                 create_SimaPro_fields,
                                 ensure_categories_are_tuples,
                                 normalize_and_add_CAS_number,
                                 normalize_simapro_biosphere_categories,
                                 remove_exchanges_with_zero_amount,
                                 set_code,
                                 transformation_units)
from ..strategies.simapro import (add_allocation_field,
                                  add_output_amount_field,
                                  add_SimaPro_categories_and_category_type,
                                  add_SimaPro_classification,
                                  drop_final_waste_flows,
                                  extract_ecoinvent_UUID_from_SimaPro_comment_field,
                                  extract_geography_from_SimaPro_name,
                                  identify_and_detoxify_SimaPro_name_of_ecoinvent_inventories)
from .base import LCIImporter

starting: str = "------------"

# Fields that identify a biosphere flow
BIOSPHERE_FLOW_ID_FIELDS: tuple[str, ...] = ("name", "categories", "unit", "location")


def _as_paths(filepaths: pathlib.Path | str | Iterable[pathlib.Path | str], suffix: str = ".csv") -> list[pathlib.Path]:
    """Accept a file, a folder (all files with ``suffix``) or a list of files."""
    if isinstance(filepaths, (str, pathlib.Path)):
        path = pathlib.Path(filepaths)
        if path.is_dir():
            paths = sorted(m for m in path.iterdir() if m.suffix.lower() == suffix)
            if not paths:
                raise ValueError("No '{}' files found in folder:\n{}".format(suffix, path))
            return paths
        return [path]
    return [pathlib.Path(m) for m in filepaths]


class SimaProLCIImporter(LCIImporter):
    """Import and standardize inventories from one or more SimaPro CSV exports.

    On creation, the CSV files are read and the SimaPro standardization strategies are applied
    (allocation of multi-output processes, normalization of units and biosphere categories, extraction of
    locations, codes, SimaPro metadata fields, ...). Afterwards, use the :class:`LCIImporter` methods
    to migrate, link and write the database.

    Parameters
    ----------
    filepaths
        A SimaPro CSV file, a folder containing CSV files, or a list of files.
    db_name
        Name of the database.
    encoding, delimiter
        Format of the SimaPro CSV files.
    link_internally
        Link exchanges to activities within the imported data at the end of the import.
    biosphere, unlinked_biosphere, linker, verbose
        See :class:`LCIImporter`.
    """

    format: str = "SimaPro CSV"

    def __init__(self,
                 filepaths: pathlib.Path | str | Iterable[pathlib.Path | str],
                 db_name: str,
                 encoding: str = "latin-1",
                 delimiter: str = "\t",
                 link_internally: bool = True,
                 biosphere: str | None = None,
                 unlinked_biosphere: str | None = None,
                 linker: Linker | None = None,
                 verbose: bool = True) -> None:
        super().__init__(db_name,
                         biosphere=biosphere,
                         unlinked_biosphere=unlinked_biosphere,
                         linker=linker,
                         verbose=verbose)
        self.filepaths: list[pathlib.Path] = _as_paths(filepaths)

        if verbose:
            print(starting + "Import inventories from SimaPro CSV:")

        for filepath in self.filepaths:
            self.data += copy.deepcopy(bw2io.importers.simapro_csv.SimaProCSVImporter(str(filepath),
                                                                                       db_name,
                                                                                       delimiter=delimiter,
                                                                                       encoding=encoding).data)

        self.strategies = self.default_strategies()
        self.apply_strategies(verbose=verbose)

        if link_internally:
            self.link_internally()

    @staticmethod
    def default_strategies() -> list:
        """The standardization steps applied to freshly imported SimaPro inventories, in order."""
        return [
            # Ensure that all categories fields of all biosphere flows are tuples
            ensure_categories_are_tuples,
            # Remove the sub category if it is 'unspecified'
            bw2io.strategies.biosphere.drop_unspecified_subcategories,
            # Brightway handles only one output per inventory: duplicate multi-output inventories, one per output
            bw2io.strategies.simapro.sp_allocate_products,
            # Remove outputs with an allocation factor of 0
            bw2io.strategies.simapro.fix_zero_allocation_products,
            # Keep the original SimaPro fields
            partial(create_SimaPro_fields, for_ds=True, for_exchanges=True),
            # Normalize biosphere categories and units to ecoinvent standard
            normalize_simapro_biosphere_categories,
            bw2io.strategies.generic.normalize_units,
            # Transform units to a common standard (e.g. kWh and kJ to MJ)
            transformation_units,
            # Extract the location of regionalized biosphere flows from their name ('GLO' if none)
            partial(add_location_to_biosphere_exchanges, select_GLO_in_name_valid_for_method_import=False),
            # Split the categories field into top and sub category (needed for linking)
            add_top_and_subcategory_fields_for_biosphere_flows,
            # Normalize and add CAS numbers
            normalize_and_add_CAS_number,
            # Extract the location of inventories and exchanges from their name
            extract_geography_from_SimaPro_name,
            # Set codes from name, unit and location (registered in the UUID registry)
            partial(set_code,
                    fields=("name", "unit", "location"),
                    overwrite=True,
                    strip=True,
                    case_insensitive=True,
                    remove_special_characters=False),
            # Final waste flows are of no use
            drop_final_waste_flows,
            # Make SimaPro metadata stored in the production exchange accessible on the inventory
            add_SimaPro_classification,
            add_SimaPro_categories_and_category_type,
            add_allocation_field,
            add_output_amount_field,
            # Exchanges with an amount of 0 do not contribute
            remove_exchanges_with_zero_amount,
            # Identify inventories that originate from ecoinvent
            extract_ecoinvent_UUID_from_SimaPro_comment_field,
            identify_and_detoxify_SimaPro_name_of_ecoinvent_inventories,
        ]


class SimaProLCIAImporter:
    """Import LCIA methods from SimaPro CSV exports and register them (with their biosphere) in Brightway.

    Example::

        lcia = SimaProLCIAImporter(lcia_folder)
        lcia.write_biosphere("biosphere3 - from SimaPro")
        lcia.write_methods(logs_dir=project.output_dir)

    Parameters
    ----------
    filepaths
        A SimaPro LCIA CSV file, a folder containing CSV files, or a list of files.
    encoding, delimiter
        Format of the SimaPro CSV files.
    """

    def __init__(self,
                 filepaths: pathlib.Path | str | Iterable[pathlib.Path | str],
                 encoding: str = "latin-1",
                 delimiter: str = "\t",
                 verbose: bool = True) -> None:
        self.filepaths: list[pathlib.Path] = _as_paths(filepaths)
        self.biosphere: str | None = None
        self.verbose: bool = verbose
        self.data: list[dict] = []

        if verbose:
            print(starting + "Importing SimaPro LCIA methods:")

        for filepath in self.filepaths:
            if verbose:
                print(filepath.name)
            self.data += bw2io.extractors.SimaProLCIACSVExtractor.extract(str(filepath), delimiter, encoding)

        if verbose:
            print("\n" + starting + "Apply strategies")

        for strategy in self.default_strategies():
            if verbose:
                print("Applying strategy: " + (getattr(strategy, "__name__", None) or strategy.func.__name__))
            self.data = strategy(copy.deepcopy(self.data))

        if verbose:
            print()

    def __repr__(self) -> str:
        return "{}(methods={})".format(type(self).__name__, len(self.data))

    def __len__(self) -> int:
        return len(self.data)

    @property
    def method_names(self) -> list[tuple[str, ...]]:
        return [m["name"] for m in self.data]

    @staticmethod
    def default_strategies() -> list:
        """The standardization steps applied to freshly imported SimaPro LCIA methods, in order."""
        return [
            ensure_categories_are_tuples,
            partial(create_SimaPro_fields, for_ds=False, for_exchanges=True),
            bw2io.strategies.lcia.set_biosphere_type,
            bw2io.strategies.biosphere.drop_unspecified_subcategories,
            normalize_simapro_biosphere_categories,
            bw2io.strategies.generic.normalize_units,
            transformation_units,
            partial(add_location_to_biosphere_exchanges, select_GLO_in_name_valid_for_method_import=True),
            add_top_and_subcategory_fields_for_biosphere_flows,
            normalize_and_add_CAS_number,
        ]

    def biosphere_flows(self, biosphere: str) -> list[dict]:
        """Unique biosphere flows characterized by the imported methods, as datasets of database ``biosphere``."""
        biosphere_mapping: dict = {}
        for imported_method in copy.deepcopy(self.data):
            for flow in imported_method["exchanges"]:
                # The amount is the characterization factor, which is not needed for the flow itself
                del flow["amount"]
                flow_ID = hp.format_values(tuple([flow[m] for m in BIOSPHERE_FLOW_ID_FIELDS]),
                                           case_insensitive=True,
                                           strip=True,
                                           remove_special_characters=False)
                biosphere_mapping[flow_ID] = dict(flow, **{"type": "natural resource" if flow["top_category"].lower() in ["raw", "natural resource"] else "emission",
                                                           "database": biosphere,
                                                           "code": str(uuid.uuid4()),
                                                           "exchanges": []})
        return list(biosphere_mapping.values())

    def write_biosphere(self, name: str) -> None:
        """Write all biosphere flows used in the methods to a new biosphere database ``name`` (replacing an existing one).

        The database is also set as Brightway's default biosphere and as target for :meth:`write_methods`.
        """
        if name in bw2data.databases:
            if self.verbose:
                print(starting + "Delete biosphere database:\n" + name + "\n")
            del bw2data.databases[name]

        if self.verbose:
            print(starting + "Data is imported into project:\n" + bw2data.projects.current + "\n")

        biosphere_dict: dict = {(v["database"], v["code"]): v for v in self.biosphere_flows(name)}

        print("\n" + starting + "Writing biosphere flows to Brightway database")
        bw2data.Database(name).write(copy.deepcopy(biosphere_dict))
        bw2data.config.p["biosphere_database"] = name
        self.biosphere = name

    def write_methods(self,
                      biosphere: str | None = None,
                      logs_dir: pathlib.Path | str | None = None,
                      append_missing_regionalized_flows: bool = True) -> None:
        """Link the methods to the biosphere database and register them in Brightway (replacing existing ones).

        Parameters
        ----------
        biosphere
            Biosphere database to link to. Defaults to the one written with :meth:`write_biosphere`.
        logs_dir
            Folder for log files of :func:`~rosetta.methods.append_missing_regionalized_flows_to_methods`.
            Defaults to the project's output directory.
        append_missing_regionalized_flows
            Add regionalized flows that are missing in a method, using the factor of the 'GLO' flow.
        """
        biosphere = biosphere or self.biosphere
        if biosphere is None:
            raise ValueError("No biosphere database given. Call 'write_biosphere' first or pass 'biosphere'.")
        if biosphere not in bw2data.databases:
            raise ValueError("Biosphere database with the name '{}' not found/not registered in the Brightway background. Available databases are:\n - {}".format(biosphere, "\n - ".join(bw2data.databases)))
        logs_path: pathlib.Path = pathlib.Path(bw2data.projects.output_dir) if logs_dir is None else pathlib.Path(logs_dir)

        # Delete methods if already existing
        for method_name in self.method_names:
            if method_name in bw2data.methods:
                del bw2data.methods[method_name]
                print("Deleted LCIA method '{}'".format(method_name))

        biosphere_list: list = [m.as_dict() for m in bw2data.Database(biosphere)]
        biosphere_dict: dict = {(m["database"], m["code"]): m for m in biosphere_list}
        biosphere_mapping: dict = {hp.format_values(tuple([m[n] for n in BIOSPHERE_FLOW_ID_FIELDS]),
                                                    case_insensitive=True,
                                                    strip=True,
                                                    remove_special_characters=False): m for m in biosphere_list}

        if self.verbose:
            print("\n" + "Applying strategy: add_top_category_factors_as_proxy_for_sub_categories")
        imported_methods = add_top_category_factors_as_proxy_for_sub_categories(self.data, biosphere_dict=biosphere_dict)

        # Add the codes of the biosphere flows to the characterization factors, so that they can be linked by code
        if self.verbose:
            print("Applying strategy: add_code_field")
        imported_methods = add_code_field(copy.deepcopy(imported_methods),
                                          mapping=biosphere_mapping,
                                          identifying_fields=BIOSPHERE_FLOW_ID_FIELDS)

        methods = bw2io.importers.base_lcia.LCIAImporter("", biosphere=biosphere)
        methods.data = copy.deepcopy(imported_methods)
        methods.apply_strategy(partial(bw2io.strategies.generic.link_iterable_by_fields,
                                       other=(obj for obj in bw2data.Database(biosphere)),
                                       fields=["code"]), verbose=self.verbose)

        if self.verbose:
            print("\n" + starting + "Writing LCIA methods to Brightway")
        methods.write_methods(overwrite=True, verbose=self.verbose)
        if self.verbose:
            print("")

        # Make sure every regionalized version of a characterized flow is part of the methods (using the 'GLO' factor)
        if append_missing_regionalized_flows:
            append_missing_regionalized_flows_to_methods(biosphere_standardized=biosphere_dict,
                                                         logs_output_path=logs_path,
                                                         verbose=self.verbose)
