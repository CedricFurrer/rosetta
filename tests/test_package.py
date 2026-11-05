import importlib
import pathlib

import pytest

import rosetta

MODULES = [
    "rosetta.helper",
    "rosetta.defaults.categories",
    "rosetta.defaults.compartments",
    "rosetta.defaults.locations",
    "rosetta.defaults.model_type",
    "rosetta.defaults.units",
    "rosetta.utils",
    "rosetta.link",
    "rosetta.lcia",
    "rosetta.lci",
    "rosetta.builder",
    "rosetta.exporter",
    "rosetta.calculation",
    "rosetta.harmonization",
    "rosetta.activity_harmonization",
    "rosetta.biosphere_harmonization",
    "rosetta.correspondence.correspondence",
]


def test_version():
    assert rosetta.__version__ == ".".join(str(m) for m in rosetta.__version_info__)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


def test_lazy_submodule_access():
    assert rosetta.lci is importlib.import_module("rosetta.lci")


def test_package_data_shipped():
    assert (pathlib.Path(rosetta.__file__).parent / "defaults" / "CAS.json").is_file()
