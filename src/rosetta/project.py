"""Brightway project handling."""

import json
import os
import pathlib

import bw2data
import pandas as pd

starting: str = "------------"


def set_brightway_directory(directory: pathlib.Path | str, verbose: bool = True) -> None:
    """Point Brightway to another base directory for its projects (instead of the default ``BRIGHTWAY2_DIR``)."""
    if verbose:
        print(starting + "BRIGHTWAY2_DIR is set to the following path:\n" + str(directory) + "\n")
    bw2data.projects._base_data_dir = str(directory)
    bw2data.projects._base_logs_dir = os.path.join(str(directory), "logs")
    bw2data.projects.db = bw2data.sqlite.SubstitutableDatabase(os.path.join(str(directory), "projects.db"),
                                                               [bw2data.project.ProjectDataset])
    bw2data.projects.set_current("default", update=False)


class BrightwayProject:
    """A Brightway project, activated on creation.

    Parameters
    ----------
    name
        Project name.
    directory
        Base directory for Brightway projects. If None, Brightway's current/default directory is used.
    new
        If True, raise an error if the project already exists.
    """

    def __init__(self,
                 name: str,
                 directory: pathlib.Path | str | None = None,
                 new: bool = False,
                 verbose: bool = True) -> None:
        self.name: str = name
        self.directory: pathlib.Path | None = None if directory is None else pathlib.Path(directory)
        self.verbose: bool = verbose

        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)
            set_brightway_directory(self.directory, verbose=verbose)

        if new and name in bw2data.projects:
            raise ValueError("Project '{}' already exists.".format(name))

        self.activate()

    def __repr__(self) -> str:
        return "{}(name={!r}, directory={!r})".format(type(self).__name__, self.name, self.directory)

    def activate(self) -> None:
        """Make this project Brightway's current project."""
        bw2data.projects.set_current(self.name)

    @property
    def output_dir(self) -> pathlib.Path:
        return pathlib.Path(bw2data.projects.output_dir)

    @property
    def databases(self) -> list[str]:
        return list(bw2data.databases)

    @property
    def methods(self) -> list[tuple[str, ...]]:
        return list(bw2data.methods)

    def has_database(self, name: str) -> bool:
        return name in bw2data.databases

    def delete_database(self, name: str) -> None:
        """Delete a database if it exists."""
        if name in bw2data.databases:
            if self.verbose:
                print(starting + "Delete database: " + name)
            del bw2data.databases[name]

    def copy_database(self, name: str, new_name: str | None = None):
        """Load a registered database into an importer (optionally under a new name) for further processing."""
        from .importers import LCIImporter
        return LCIImporter.from_brightway(name, new_name=new_name)

    def activity_metadata(self, database: str) -> list[dict]:
        """List of activities of ``database`` with their (SimaPro) metadata."""
        data: list[dict] = []
        if database not in bw2data.databases:
            return []
        for act in bw2data.Database(database):
            comment: dict = act.get("simapro metadata", {})
            data += [{"database": database,
                      "activity_code": act.key[0],
                      "activity_name": act.get("name"),
                      "activity_SimaPro_name": act.get("SimaPro_name"),
                      "activity_location": act.get("location"),
                      "activity_unit": act.get("unit"),
                      "activity_SimaPro_unit": act.get("SimaPro_unit"),
                      "SimaPro_classification": " | ".join(["'" + m + "'" for m in act.get("SimaPro_categories", ())]),
                      **{"Field_" + k: str(v) for k, v in comment.items()}}]
        return data

    def export_overview(self, biosphere: str, output_dir: pathlib.Path | str | None = None) -> None:
        """Write the biosphere flows of ``biosphere`` and the names of all LCIA methods to Excel files.

        Raises an error (and writes 'Duplicated_flows_in_biosphere3.xlsx') if the biosphere contains duplicated flows.
        """
        output_path: pathlib.Path = self.output_dir if output_dir is None else pathlib.Path(output_dir)

        if self.verbose:
            print(starting + "Write biosphere flows and LCIA method names to Excel")

        biosphere_orig: list[dict] = [m.as_dict() for m in bw2data.Database(biosphere)]

        # Remove the duplicates based on the columns that make the flows unique
        group_cols = ("name", "categories", "unit", "location") + ("type", "CAS number",)
        biosphere_df = pd.DataFrame(biosphere_orig).drop_duplicates(group_cols)
        biosphere_df.to_excel(output_path / "Biosphere_elementary_flows.xlsx")

        if self.verbose:
            print("Table with biosphere flows saved to:\n" + str(output_path / "Biosphere_elementary_flows.xlsx") + "\n")

        # Check if there are duplicates in the biosphere
        table = pd.DataFrame({m: [n[m] for n in biosphere_df.to_dict("records")] for m in ("name", "categories", "unit", "location")})
        duplicates = table[table.duplicated()]

        if not duplicates.empty:
            duplicates.to_excel(output_path / "Duplicated_flows_in_biosphere3.xlsx")
            raise ValueError("There are duplicates in the database '" + biosphere + "'. Check file 'Duplicated_flows_in_biosphere.xlsx' to see which flows are duplicated.")

        pd.DataFrame({"LCIA_method_names": [m for m in bw2data.methods]}).to_excel(output_path / "Available_LCIA_method_names.xlsx")

        if self.verbose:
            print("Table with LCIA method names saved to:\n" + str(output_path / "Available_LCIA_method_names.xlsx") + "\n")

    def export_database_to_json(self, database: str, filepath: pathlib.Path | str) -> None:
        """Write all datasets of ``database`` to a JSON file (index -> dataset)."""
        data: dict = {idx: dict(m) for idx, m in enumerate(bw2data.Database(database))}
        with open(filepath, "w") as outfile:
            outfile.write(json.dumps(data, indent=4))
