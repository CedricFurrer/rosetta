"""Importers for ecoinvent ecospold2 (XML) inventories and ecoinvent LCIA method files."""

import copy
import pathlib
from functools import partial

import bw2data
import bw2io
import pandas as pd

from ..linking import Linker, unlink
from ..strategies.common import (add_top_and_subcategory_fields_for_biosphere_flows,
                                 create_SimaPro_fields,
                                 ensure_categories_are_tuples,
                                 normalize_and_add_CAS_number,
                                 normalize_simapro_biosphere_categories,
                                 transformation_units)
from ..strategies.ecospold import (add_GLO_to_biosphere_exchanges,
                                   assign_categories_from_XML_to_biosphere_flows,
                                   assign_flow_field_as_code,
                                   flip_sign_of_waste_flows,
                                   modify_fields_to_SimaPro_standard)
from .base import LCIImporter

starting: str = "------------"


def read_ecoinvent_biosphere(filepath: pathlib.Path | str, biosphere: str) -> list[dict]:
    """Read the elementary flows of an ecoinvent 'ElementaryExchanges.xml' file as datasets of database ``biosphere``."""
    from lxml import objectify
    from bw2io.importers.ecospold2_biosphere import EMISSIONS_CATEGORIES

    # Adapted from the Brightway ecospold2 biosphere importer
    def extract_flow_data(o):
        ds = {
            "categories": (
                o.compartment.compartment.text,
                o.compartment.subcompartment.text,
            ),
            "top_category": o.compartment.compartment.text,
            "sub_category": o.compartment.subcompartment.text,
            "code": o.get("id"),
            "CAS number": o.get("casNumber"),
            "name": o.name.text,
            "location": "GLO",
            "database": biosphere,
            "exchanges": [],
            "unit": o.unitName.text,
        }
        ds["type"] = EMISSIONS_CATEGORIES.get(ds["categories"][0], ds["categories"][0])
        return ds

    with open(filepath, encoding="utf-8") as file:
        root = objectify.parse(file).getroot()
    flow_data = bw2data.utils.recursive_str_to_unicode([extract_flow_data(ds) for ds in root.iterchildren()])

    flow_data = ensure_categories_are_tuples(flow_data)
    flow_data = bw2io.strategies.biosphere.drop_unspecified_subcategories(flow_data)
    flow_data = normalize_and_add_CAS_number(flow_data)
    flow_data = create_SimaPro_fields(flow_data, for_ds=True, for_exchanges=False)
    flow_data = normalize_simapro_biosphere_categories(flow_data)
    flow_data = bw2io.strategies.generic.normalize_units(flow_data)
    flow_data = transformation_units(flow_data)
    flow_data = add_top_and_subcategory_fields_for_biosphere_flows(flow_data)
    return flow_data


class EcospoldLCIImporter(LCIImporter):
    """Import ecoinvent ecospold2 (XML) inventories and bring them to the SimaPro standard used by rosetta.

    Parameters
    ----------
    dirpath
        The ecoinvent 'datasets' folder. 'MasterData/ElementaryExchanges.xml' must exist next to it.
    db_name
        Name of the database.
    biosphere
        Name of the biosphere database the elementary flows (and biosphere exchanges) are assigned to.
    model_type, process_type
        ecoinvent system model and process type, used to create the SimaPro fields
        (e.g. ``"cutoff"`` and ``"unit"``).
    """

    format: str = "Ecospold2"

    def __init__(self,
                 dirpath: pathlib.Path | str,
                 db_name: str,
                 biosphere: str,
                 model_type: str,
                 process_type: str,
                 unlinked_biosphere: str | None = None,
                 linker: Linker | None = None,
                 verbose: bool = True) -> None:
        super().__init__(db_name,
                         biosphere=biosphere,
                         unlinked_biosphere=unlinked_biosphere,
                         linker=linker,
                         verbose=verbose)
        self.dirpath: pathlib.Path = pathlib.Path(dirpath)
        self.model_type: str = model_type
        self.process_type: str = process_type

        elementary_exchanges_filepath: pathlib.Path = self.dirpath.parent / "MasterData" / "ElementaryExchanges.xml"
        if not elementary_exchanges_filepath.exists():
            raise ValueError("Filepath to XML data for elementary exchanges does not exist. Please point to file 'ElementaryExchanges.xml'.")

        if verbose:
            print(starting + "Import database from XML: " + db_name)

        # Read and process with all Brightway ecospold2 strategies
        importer = bw2io.SingleOutputEcospold2Importer(str(self.dirpath), db_name, use_mp=False)
        importer.apply_strategies(verbose=verbose)
        self.data = importer.data
        self.applied_strategies = list(getattr(importer, "applied_strategies", []))

        self.biosphere_flows: list[dict] = read_ecoinvent_biosphere(elementary_exchanges_filepath, biosphere)

        self.strategies = self.default_strategies()
        self.apply_strategies(verbose=verbose)

    def default_strategies(self) -> list:
        """rosetta's steps applied after the Brightway ecospold2 strategies, in order."""
        return [
            assign_flow_field_as_code,
            normalize_and_add_CAS_number,
            partial(assign_categories_from_XML_to_biosphere_flows, biosphere_flows=self.biosphere_flows),
            bw2io.strategies.biosphere.drop_unspecified_subcategories,
            partial(add_top_and_subcategory_fields_for_biosphere_flows, remove_initial_category_field=False),
            partial(modify_fields_to_SimaPro_standard, model_type=self.model_type, process_type=self.process_type),
            # ecoinvent only uses 'GLO' biosphere flows; set it explicitly to be consistent with SimaPro flows
            add_GLO_to_biosphere_exchanges,
            flip_sign_of_waste_flows,
            # Relink everything on name, unit and location
            unlink,
            partial(self.linker.link_internally, production=True, substitution=True, technosphere=True, relink=False),
        ]

    def biosphere_flows_used(self, biosphere: str | None = None) -> list[dict]:
        """Unique biosphere flows used by the exchanges of this database, as datasets of database ``biosphere``."""
        biosphere = biosphere or self.biosphere
        data: list[dict] = add_top_and_subcategory_fields_for_biosphere_flows(copy.deepcopy(self.data))
        flows: dict = {}
        for ds in data:
            for exc in ds["exchanges"]:
                if exc["type"] == "biosphere":
                    key: tuple = (exc["name"], exc["top_category"], exc["sub_category"], exc["unit"], exc["location"])
                    if key not in flows:
                        flows[key] = {**exc, "database": biosphere}
        return list(flows.values())


class EcoinventLCIAImporter:
    """Import LCIA methods from an ecoinvent LCIA Excel file and register them in Brightway.

    The characterization factors are linked to the flows of ``biosphere`` by name and categories.
    """

    def __init__(self,
                 filepath: pathlib.Path | str,
                 biosphere: str,
                 ecoinvent_version: str | None = None) -> None:
        self.filepath: pathlib.Path = pathlib.Path(filepath)
        self.biosphere: str = biosphere
        self.ecoinvent_version: str | None = ecoinvent_version
        self.data: list[dict] = self._read()

    def __repr__(self) -> str:
        return "{}(methods={})".format(type(self).__name__, len(self.data))

    def __len__(self) -> int:
        return len(self.data)

    def _read(self) -> list[dict]:
        # Adapted from the Brightway ecoinvent 'get_ecoinvent_release' function
        dfs: dict = pd.read_excel(self.filepath, sheet_name=None)
        units_mapping: dict = {(row["Method"], row["Category"], row["Indicator"]): row["Indicator Unit"] for idx, row in dfs["Indicators"].iterrows()}

        mapping: dict = {}
        for flow in bw2data.Database(self.biosphere):
            mapping[(flow["name"],) + tuple(flow["categories"])] = flow.key
            if flow["name"].startswith("[Deleted]"):
                mapping[(flow["name"].replace("[Deleted]", ""),) + tuple(flow["categories"])] = flow.key

        def drop_unspecified(a: str, b: str, c: str) -> tuple:
            return (a, b) if c.lower() == "unspecified" else (a, b, c)

        lcia_data: dict = {}
        for idx, row in dfs["CFs"].replace({float("NaN"): None}).iterrows():
            impact_category: tuple[str, str, str] = (row["Method"], row["Category"], row["Indicator"])
            if row["CF"] is None:
                continue
            if impact_category not in lcia_data:
                lcia_data[impact_category] = []
            ID = mapping.get(drop_unspecified(row["Name"], row["Compartment"], row["Subcompartment"]))
            if ID is None:
                raise ValueError("Could not find biosphere flow '{}' in biosphere '{}'".format(drop_unspecified(row["Name"], row["Compartment"], row["Subcompartment"]), self.biosphere))
            lcia_data[impact_category] += [(ID, float(row["CF"]))]

        return [{"name": method_tuple,
                 "unit": units_mapping.get(method_tuple, "Unknown"),
                 "filepath": str(self.filepath),
                 "ecoinvent_version": "ecoinvent version not indicated" if self.ecoinvent_version is None else self.ecoinvent_version,
                 "database": self.biosphere,
                 "exchanges": exchanges} for method_tuple, exchanges in lcia_data.items()]

    def write_methods(self) -> None:
        """Register all methods in Brightway (replacing existing ones)."""
        for item in self.data:
            if item["name"] in bw2data.methods:
                del bw2data.methods[item["name"]]
            method = bw2data.Method(item["name"])
            method.register(unit=item["unit"],
                            filepath=item["filepath"],
                            ecoinvent_version=item["ecoinvent_version"],
                            database=item["database"])
            method.write(item["exchanges"])
