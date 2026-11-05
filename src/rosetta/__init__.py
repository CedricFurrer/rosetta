"""rosetta: work with SimaPro data (inventories and LCIA methods) in Brightway (v2).

Typical workflow::

    from rosetta import BrightwayProject, SimaProLCIAImporter, SimaProLCIImporter

    project = BrightwayProject("my project", directory=projects_dir)

    lcia = SimaProLCIAImporter(lcia_folder)
    lcia.write_biosphere("biosphere3 - from SimaPro")
    lcia.write_methods()

    db = SimaProLCIImporter(ecoinvent_csv, "ecoinvent v3.11 - SimaPro",
                            biosphere="biosphere3 - from SimaPro",
                            unlinked_biosphere="biosphere3 - from SimaPro - unlinked")
    db.migrate(migration_xlsx).link_biosphere().add_unlinked_to_biosphere().link_internally()
    db.statistics()
    db.write(overwrite=True)

The public classes are available at the top level; they are imported lazily on first access, so
``import rosetta`` stays fast and does not load torch or sentence-transformers until needed.
"""

import importlib

from .__version__ import __version__, __version_info__

# Public name -> module that defines it
_EXPORTS: dict[str, str] = {
    "BrightwayProject": ".project",
    "set_brightway_directory": ".project",
    "LCIImporter": ".importers",
    "SimaProLCIImporter": ".importers",
    "SimaProLCIAImporter": ".importers",
    "EcospoldLCIImporter": ".importers",
    "EcoinventLCIAImporter": ".importers",
    "read_ecoinvent_biosphere": ".importers",
    "Linker": ".linking",
    "Migration": ".migration",
    "Inventory": ".builder",
    "Exchange": ".builder",
    "Uncertainty": ".builder",
    "SimaProCSVExporter": ".exporter",
    "LCACalculation": ".calculation",
    "ActivityDefinition": ".harmonization",
    "ActivityHarmonization": ".harmonization",
    "BiosphereDefinition": ".harmonization",
    "BiosphereHarmonization": ".harmonization",
    "Correspondence": ".harmonization",
}

_SUBMODULES: tuple[str, ...] = (
    "builder",
    "calculation",
    "defaults",
    "exporter",
    "harmonization",
    "importers",
    "linking",
    "methods",
    "migration",
    "project",
    "strategies",
)

__all__: list[str] = ["__version__", "__version_info__", *_EXPORTS, *_SUBMODULES]


def __getattr__(name: str):
    if name in _EXPORTS:
        return getattr(importlib.import_module(_EXPORTS[name], __name__), name)
    if name in _SUBMODULES:
        return importlib.import_module("." + name, __name__)
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
