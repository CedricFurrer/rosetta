import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "simapro"
BIOSPHERE = "biosphere - SimaPro"
UNLINKED = "biosphere - SimaPro - unlinked"


@pytest.fixture(scope="session")
def fixtures() -> pathlib.Path:
    return FIXTURES


@pytest.fixture(scope="session")
def brightway_project(tmp_path_factory):
    """A fresh Brightway project in a temporary directory, with a fresh UUID registry."""
    mp = pytest.MonkeyPatch()
    workdir = tmp_path_factory.mktemp("brightway")
    mp.setenv("ROSETTA_UUID_FILE", str(workdir / "UUIDs.xlsx"))

    from rosetta import BrightwayProject
    project = BrightwayProject("rosetta tests", directory=workdir / "projects", verbose=False)
    yield project
    mp.undo()


@pytest.fixture(scope="session")
def written_databases(brightway_project, fixtures):
    """Run the SimaPro workflow on the fixtures: LCIA methods + biosphere, background and foreground database."""
    from rosetta import SimaProLCIAImporter, SimaProLCIImporter

    lcia = SimaProLCIAImporter(fixtures / "lcia", verbose=False)
    lcia.write_biosphere(BIOSPHERE)
    lcia.write_methods(logs_dir=brightway_project.output_dir)

    background = SimaProLCIImporter(fixtures / "lci" / "a_background.csv", "background",
                                    biosphere=BIOSPHERE, unlinked_biosphere=UNLINKED, verbose=False)
    background.link_biosphere().add_unlinked_to_biosphere().link_internally()
    background.write(overwrite=True)

    farm = SimaProLCIImporter(fixtures / "lci" / "b_farm.csv", "farm",
                              biosphere=BIOSPHERE, unlinked_biosphere=UNLINKED, verbose=False)
    farm.migrate(fixtures / "lci" / "b_farm_migration.xlsx")
    farm.link_biosphere().add_unlinked_to_biosphere().link_internally().link_to("background", production=False)
    farm.write(overwrite=True)

    return {"lcia": lcia, "background": background, "farm": farm}
