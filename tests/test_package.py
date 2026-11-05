import importlib
import pathlib

import pytest

import rosetta

MODULES = [
    "rosetta.builder",
    "rosetta.calculation",
    "rosetta.defaults.categories",
    "rosetta.defaults.compartments",
    "rosetta.defaults.locations",
    "rosetta.defaults.model_type",
    "rosetta.defaults.units",
    "rosetta.exporter",
    "rosetta.harmonization",
    "rosetta.harmonization.activity",
    "rosetta.harmonization.biosphere",
    "rosetta.harmonization.correspondence",
    "rosetta.harmonization.flows",
    "rosetta.harmonization.sbert",
    "rosetta.importers",
    "rosetta.linking",
    "rosetta.methods",
    "rosetta.migration",
    "rosetta.project",
    "rosetta.strategies",
]


def test_version():
    assert rosetta.__version__ == ".".join(str(m) for m in rosetta.__version_info__)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", sorted(rosetta._EXPORTS))
def test_public_names(name):
    assert getattr(rosetta, name).__name__ == name


def test_unknown_attribute():
    with pytest.raises(AttributeError):
        rosetta.does_not_exist


def test_package_data_shipped():
    assert (pathlib.Path(rosetta.__file__).parent / "defaults" / "CAS.json").is_file()
