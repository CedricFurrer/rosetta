"""Build standardized (SimaPro-compatible) Brightway inventories and exchanges.

Example::

    electricity = Exchange.from_activity("ecoinvent v3.11", "a1b2...", type="technosphere", amount=0.3)
    co2 = Exchange(name="Carbon dioxide, fossil", simapro_name="Carbon dioxide, fossil",
                   categories=("air",), simapro_categories=("Emissions to air",),
                   unit="kilogram", location="GLO", amount=1.2, type="biosphere",
                   uncertainty=Uncertainty("lognormal distr.", scale=1.1))
    inventory = Inventory(name="My product", simapro_name="My product {CH}", simapro_category_type="material",
                          unit="kilogram", location="CH", simapro_classification=("Agriculture",),
                          amount=1, database="my database", exchanges=[electricity, co2])
    dataset = inventory.to_dict()
"""

import copy
import math
import uuid
from dataclasses import dataclass, field
from typing import Self

import bw2data

from .defaults.compartments import (SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING,
                                    SIMAPRO_PRODUCT_COMPARTMENTS,
                                    SIMAPRO_SUBSTITUTION_COMPARTMENTS,
                                    SIMAPRO_TECHNOSPHERE_COMPARTMENTS)
from .defaults.units import backward_unit_normalization_mapping

UNCERTAINTY_TYPES: dict[str, int] = {"undefined": 0,
                                     "no uncertainty": 1,
                                     "lognormal distr.": 2,
                                     "normal distr.": 3,
                                     "uniform distr.": 4,
                                     "triangular distr.": 5,
                                     "bernoulli distr.": 6,
                                     "discrete uniform": 7,
                                     "weibull": 8,
                                     "gamma": 9,
                                     "beta distr.": 10,
                                     "generalized extreme value": 11,
                                     "student's T": 12}

# Parameters that need to be given for each uncertainty type
REQUIRED_UNCERTAINTY_FIELDS: dict[str, list[str]] = {"undefined": ["loc"],
                                                     "no uncertainty": ["loc"],
                                                     "lognormal distr.": ["negative", "loc", "scale"],
                                                     "normal distr.": ["negative", "loc", "scale"],
                                                     "uniform distr.": ["negative", "minimum", "maximum"],
                                                     "triangular distr.": ["negative", "minimum", "maximum"],
                                                     "bernoulli distr.": ["loc"],
                                                     "discrete uniform": ["maximum"],
                                                     "weibull": ["scale", "shape"],
                                                     "gamma": ["scale", "shape"],
                                                     "beta distr.": ["loc", "shape"],
                                                     "generalized extreme value": ["loc", "scale", "shape"],
                                                     "student's T": ["shape"]}

EXCHANGE_TYPES: tuple[str, ...] = ("technosphere", "biosphere", "substitution")


def _simapro_unit(unit: str, simapro_unit: str | None, field_name: str) -> str:
    if simapro_unit is not None:
        return simapro_unit
    mapped: str | None = backward_unit_normalization_mapping.get(unit)
    if mapped is None:
        raise ValueError("'{0}' could not be mapped from unit '{1}'. Provide '{0}'.".format(field_name, unit))
    return mapped


def _add_extra(target: dict, extra: dict, allow_overwrite: bool, kind: str) -> dict:
    for k, v in extra.items():
        if not allow_overwrite and k in target:
            raise ValueError("Key/value pair already exists in {0}. Problematic key: '{1}'.\n\nEither set 'allow_overwrite' to True or do NOT pass the key again via 'extra'.".format(kind, k))
        target[k] = v
    return target


@dataclass
class Uncertainty:
    """Uncertainty of an exchange amount.

    Parameters
    ----------
    type
        Name (e.g. ``"lognormal distr."``) or Brightway number (e.g. ``2``) of the distribution. Types above 5 are not supported.
    scale, shape, minimum, maximum
        Distribution parameters. For lognormal, ``scale`` is the geometric variance (SimaPro's squared geometric
        standard deviation); for normal, the variance. They are transformed to Brightway's parameters unless
        ``brightway_parameters`` is True.
    brightway_parameters
        The parameters are already in Brightway form (e.g. taken from an existing inventory) and are used as is.
    """

    type: str | int | float = "undefined"
    scale: float | None = None
    shape: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    brightway_parameters: bool = False

    @property
    def type_name(self) -> str:
        if isinstance(self.type, (int, float)) and not isinstance(self.type, bool):
            reverse: dict[int, str] = {v: k for k, v in UNCERTAINTY_TYPES.items()}
            if reverse.get(self.type) is None:
                raise ValueError("Uncertainty type '" + str(self.type) + "' needs to be one of the following numbers --> " + str(list(reverse)) + ". Otherwise, it can not be mapped properly.")
            return reverse[int(self.type)]
        if self.type not in UNCERTAINTY_TYPES:
            raise TypeError("Uncertainty type '" + str(self.type) + "' is not valid. Choose one from the list -->\n  - " + "\n  - ".join(UNCERTAINTY_TYPES))
        return self.type

    def to_dict(self, amount: float) -> dict:
        """Brightway uncertainty fields ('uncertainty type', 'loc', 'scale', ...) for an exchange with ``amount``."""
        name: str = self.type_name
        number: int = UNCERTAINTY_TYPES[name]
        if number > 5:
            raise NotImplementedError("Uncertainty type '" + name + "' is not supported because it can not be used in Brightway LCA calculations.")

        negative: bool | None = amount < 0 if number in (2, 3, 4, 5) else None
        given: dict = {"negative": negative, "loc": amount, "scale": self.scale, "shape": self.shape,
                       "minimum": self.minimum, "maximum": self.maximum}
        missing: list[str] = [m for m in REQUIRED_UNCERTAINTY_FIELDS[name] if given[m] is None]
        if missing:
            raise TypeError("Uncertainty type '" + name + "' requires " + str(tuple(REQUIRED_UNCERTAINTY_FIELDS[name])) + " as input(s), but " + str(tuple(missing)) + " is/are not provided.")

        if self.brightway_parameters:
            params: dict = given
        else:
            params = {"negative": negative,
                      "loc": math.log(abs(amount)) if number == 2 else amount,
                      "scale": math.log(math.sqrt(self.scale)) if number == 2 else (math.sqrt(self.scale) if number == 3 else None),
                      "shape": self.shape,
                      "minimum": self.minimum,
                      "maximum": self.maximum}
            not_transformed: list[str] = [m for m in REQUIRED_UNCERTAINTY_FIELDS[name] if params[m] is None]
            if not_transformed:
                raise TypeError("Transformation of values for required fields " + str(tuple(not_transformed)) + " for uncertainty type '" + name + "' yielded None values/could not be done.")

        return {"uncertainty type": number, **{k: v for k, v in params.items() if v is not None}}


@dataclass
class Exchange:
    """A technosphere, substitution or biosphere exchange.

    If ``database`` and ``code`` are given, the exchange is linked to that activity/flow.
    ``extra`` holds additional key/value pairs for the exchange dict. For technosphere and substitution exchanges,
    ``simapro_categories`` must be a SimaPro compartment, unless ``validate_categories`` is False.
    """

    name: str
    simapro_name: str
    categories: tuple
    simapro_categories: tuple
    unit: str
    location: str
    amount: float
    type: str
    simapro_unit: str | None = None
    database: str | None = None
    code: str | None = None
    uncertainty: Uncertainty = field(default_factory=Uncertainty)
    extra: dict = field(default_factory=dict)
    allow_overwrite: bool = False
    validate_categories: bool = True

    def __post_init__(self) -> None:
        if self.type not in EXCHANGE_TYPES:
            raise ValueError("Exchange type has wrong value. Needs to be one of {} but is currently '{}'".format(EXCHANGE_TYPES, self.type))

    @classmethod
    def from_activity(cls,
                      database: str,
                      code: str,
                      type: str,
                      amount: float,
                      uncertainty: Uncertainty | None = None,
                      extra: dict | None = None,
                      allow_overwrite: bool = False) -> Self:
        """Exchange linked to an existing activity of a registered database, taking name, unit, location etc. from it."""
        ds = bw2data.Database(database).get(code)
        return cls(name=ds["name"],
                   simapro_name=ds["SimaPro_name"],
                   categories=ds["SimaPro_categories"],
                   simapro_categories=ds["SimaPro_categories"],
                   unit=ds["unit"],
                   location=ds["location"],
                   amount=amount,
                   type=type,
                   simapro_unit=ds["SimaPro_unit"],
                   database=database,
                   code=code,
                   uncertainty=Uncertainty() if uncertainty is None else uncertainty,
                   extra={} if extra is None else extra,
                   allow_overwrite=allow_overwrite,
                   validate_categories=False)

    def _validate_simapro_categories(self) -> None:
        allowed: dict[str, list[tuple]] = {"technosphere": [(v,) for v in SIMAPRO_TECHNOSPHERE_COMPARTMENTS.values()],
                                           "substitution": [(v,) for v in SIMAPRO_SUBSTITUTION_COMPARTMENTS.values()]}
        if self.type in allowed and self.simapro_categories not in allowed[self.type]:
            raise ValueError("The SimaPro category provided for the {} exchange can not be accepted because it does not match one of the baseline SimaPro categories.\n\nCurrent category: {}\nAccepted categories: {}".format(self.type, self.simapro_categories, allowed[self.type]))

    def to_dict(self) -> dict:
        """The exchange as a Brightway exchange dict."""
        if self.validate_categories:
            self._validate_simapro_categories()
        exc: dict = {"name": self.name,
                     "SimaPro_name": self.simapro_name,
                     "type": self.type,
                     "categories": self.categories,
                     "SimaPro_categories": self.simapro_categories,
                     "unit": self.unit,
                     "SimaPro_unit": _simapro_unit(self.unit, self.simapro_unit, "simapro_unit"),
                     "location": self.location,
                     "amount": self.amount}
        if self.database is not None and self.code is not None:
            exc["input"] = (self.database, self.code)
        exc |= self.uncertainty.to_dict(self.amount)
        return _add_extra(exc, self.extra, self.allow_overwrite, "exchange")


@dataclass
class Inventory:
    """An inventory (activity) with its production exchange and further exchanges.

    ``amount`` is the output amount; with an ``allocation`` factor below 1, the production amount is
    ``amount / allocation``. If ``categories`` is None, it is derived from ``simapro_category_type``.
    ``extra`` holds additional key/value pairs for the inventory dict.
    """

    name: str
    simapro_name: str
    simapro_category_type: str
    unit: str
    location: str
    simapro_classification: tuple
    amount: float
    database: str
    categories: tuple | None = None
    simapro_unit: str | None = None
    allocation: float = 1
    type: str = "process"
    code: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchanges: list[Exchange | dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    allow_overwrite: bool = False

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("'amount' can not be 0 and can not be negative but is currently " + str(self.amount) + ".")
        if self.allocation > 1 or self.allocation <= 0:
            raise ValueError("'allocation' must be greater than 0 and smaller or equal to 1 but is currently '" + str(self.allocation) + "'.")
        if self.simapro_category_type not in SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING:
            raise ValueError("Category type '" + self.simapro_category_type + "' is not accepted. It needs to be one of " + str(list(SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING)))

    def add_exchange(self, exchange: Exchange | dict) -> Self:
        self.exchanges.append(exchange)
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.database, self.code)

    def to_dict(self) -> dict:
        """The inventory as a Brightway dataset dict, including its production exchange."""
        compartment: str = SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING[self.simapro_category_type]
        inv: dict = {"name": self.name,
                     "SimaPro_name": self.simapro_name,
                     "categories": self.categories if self.categories is not None else (compartment,),
                     "SimaPro_categories": (compartment,),
                     "SimaPro_category_type": self.simapro_category_type,
                     "unit": self.unit,
                     "SimaPro_unit": _simapro_unit(self.unit, self.simapro_unit, "simapro_unit"),
                     "location": self.location,
                     "SimaPro_classification": self.simapro_classification,
                     "production amount": self.amount / self.allocation,
                     "output amount": self.amount,
                     "allocation": self.allocation,
                     "database": self.database,
                     "type": self.type,
                     "code": self.code}

        production: dict = copy.deepcopy(inv)
        production["amount"] = self.amount / self.allocation
        production["type"] = "production"
        production["allocation"] = self.allocation * 100
        production["SimaPro_categories"] = (SIMAPRO_PRODUCT_COMPARTMENTS["products"],)
        production["input"] = self.key
        del production["production amount"]
        del production["SimaPro_category_type"]

        inv["exchanges"] = [production] + [m.to_dict() if isinstance(m, Exchange) else m for m in self.exchanges]
        return _add_extra(inv, self.extra, self.allow_overwrite, "inventory")
