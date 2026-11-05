"""Strategies: functions that take a list of datasets (dicts) and return the modified list.

They are applied by the importers, but can also be used directly, e.g. ``importer.apply(strategy, **kwargs)``.
"""

from .common import *  # noqa: F401,F403
from .ecospold import *  # noqa: F401,F403
from .simapro import *  # noqa: F401,F403
