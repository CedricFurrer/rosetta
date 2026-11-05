"""rosetta: functions to work with SimaPro data in Brightway (v2).

Submodules are loaded lazily on first access, so ``import rosetta`` stays fast
and does not pull in heavy dependencies (torch, sentence-transformers, ...)
until they are needed:

    import rosetta
    rosetta.lci.import_SimaPro_LCI_inventories(...)

    # or, equivalently
    from rosetta.lci import import_SimaPro_LCI_inventories
"""

import importlib

from .__version__ import __version__, __version_info__

_SUBMODULES: tuple = (
    "activity_harmonization",
    "biosphere_harmonization",
    "builder",
    "calculation",
    "correspondence",
    "defaults",
    "exporter",
    "harmonization",
    "helper",
    "lci",
    "lcia",
    "link",
    "utils",
)

__all__: list = ["__version__", "__version_info__", *_SUBMODULES]


def __getattr__(name: str):
    if name in _SUBMODULES:
        return importlib.import_module("." + name, __name__)
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


def __dir__() -> list:
    return sorted(set(globals()) | set(_SUBMODULES))
