"""Unit tests that need no Brightway project: builder, migration, linking."""

import math

import bw2io
import pytest

from rosetta.builder import Exchange, Inventory, Uncertainty
from rosetta.linking import Linker, unlink, unlinked_summary
from rosetta.migration import Migration


# ---------------------------------------------------------------- builder

def make_exchange(**kwargs) -> Exchange:
    defaults = dict(name="Diesel", simapro_name="Diesel {CH}", categories=("Materials/fuels",),
                    simapro_categories=("Materials/fuels",), unit="kilogram", location="CH", amount=2.0, type="technosphere")
    return Exchange(**{**defaults, **kwargs})


def test_exchange_to_dict():
    exc = make_exchange(database="db", code="abc", extra={"comment": "note"}).to_dict()
    assert exc == {"name": "Diesel", "SimaPro_name": "Diesel {CH}", "type": "technosphere",
                   "categories": ("Materials/fuels",), "SimaPro_categories": ("Materials/fuels",),
                   "unit": "kilogram", "SimaPro_unit": "kg", "location": "CH", "amount": 2.0,
                   "input": ("db", "abc"), "uncertainty type": 0, "loc": 2.0, "comment": "note"}


def test_lognormal_uncertainty_is_transformed():
    exc = make_exchange(uncertainty=Uncertainty("lognormal distr.", scale=1.21)).to_dict()
    assert exc["uncertainty type"] == 2
    assert exc["loc"] == pytest.approx(math.log(2.0))
    assert exc["scale"] == pytest.approx(math.log(math.sqrt(1.21)))
    assert exc["negative"] is False


def test_uncertainty_by_number_and_brightway_parameters():
    exc = make_exchange(uncertainty=Uncertainty(3, scale=0.5, brightway_parameters=True)).to_dict()
    assert exc["uncertainty type"] == 3 and exc["scale"] == 0.5 and exc["loc"] == 2.0


def test_uncertainty_missing_parameter():
    with pytest.raises(TypeError, match="requires"):
        make_exchange(uncertainty=Uncertainty("uniform distr.", minimum=1)).to_dict()


def test_exchange_validation():
    with pytest.raises(ValueError, match="Exchange type"):
        make_exchange(type="production")
    with pytest.raises(ValueError, match="SimaPro category"):
        make_exchange(simapro_categories=("Emissions to air",)).to_dict()
    with pytest.raises(ValueError, match="already exists"):
        make_exchange(extra={"amount": 3}).to_dict()
    assert make_exchange(extra={"amount": 3}, allow_overwrite=True).to_dict()["amount"] == 3


def test_inventory_to_dict():
    inv = Inventory(name="Grain", simapro_name="Grain {CH}", simapro_category_type="material", unit="kilogram",
                    location="CH", simapro_classification=("Agriculture",), amount=8, database="db", allocation=0.8,
                    code="c1", exchanges=[make_exchange()])
    ds = inv.to_dict()
    assert ds["production amount"] == pytest.approx(10)
    assert ds["output amount"] == 8
    assert ds["categories"] == ("Materials/fuels",)
    production, technosphere = ds["exchanges"]
    assert production["type"] == "production" and production["input"] == ("db", "c1")
    assert production["allocation"] == pytest.approx(80)
    assert production["SimaPro_categories"] == ("Products",)
    assert "production amount" not in production and "SimaPro_category_type" not in production
    assert technosphere["name"] == "Diesel"


def test_inventory_validation():
    kwargs = dict(name="X", simapro_name="X", unit="kilogram", location="CH", simapro_classification=(), database="db")
    with pytest.raises(ValueError, match="amount"):
        Inventory(simapro_category_type="material", amount=0, **kwargs)
    with pytest.raises(ValueError, match="allocation"):
        Inventory(simapro_category_type="material", amount=1, allocation=1.5, **kwargs)
    with pytest.raises(ValueError, match="Category type"):
        Inventory(simapro_category_type="unknown", amount=1, **kwargs)
    assert Inventory(simapro_category_type="material", amount=1, **kwargs).code != Inventory(simapro_category_type="material", amount=1, **kwargs).code


# ---------------------------------------------------------------- migration

def datasets() -> list[dict]:
    return [{"name": "A", "unit": "kilogram", "location": "CH", "database": "db", "code": "a", "production amount": 1,
             "exchanges": [{"name": "Methane", "unit": "kilogram", "type": "biosphere", "amount": 2.0, "loc": 2.0},
                           {"name": "CO2", "unit": "kilogram", "type": "biosphere", "amount": 1.0}]}]


def test_migration_splits_and_scales_exchanges():
    migration = Migration.from_dict({"fields": ["name"],
                                     "data": [[["Methane"], [[{"name": "Methane, fossil"}, 0.25], [{"name": "Methane, biogenic"}, 0.75]]]]})
    assert len(migration) == 1
    data = migration.apply(datasets())
    excs = data[0]["exchanges"]
    assert [(e["name"], e["amount"]) for e in excs] == [("Methane, fossil", 0.5), ("Methane, biogenic", 1.5), ("CO2", 1.0)]
    assert excs[0]["loc"] == 0.5


def test_migration_from_excel(tmp_path):
    import pandas as pd
    filepath = tmp_path / "migration.xlsx"
    pd.DataFrame([{"FROM_name": "CO2", "TO_name": "Carbon dioxide", "multiplier": 2}]).to_excel(filepath, index=False)
    data = Migration.from_file(filepath).apply(datasets())
    assert data[0]["exchanges"][1] == {"name": "Carbon dioxide", "unit": "kilogram", "type": "biosphere", "amount": 2.0}


def test_migration_rejects_unknown_file_type(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        Migration.from_file(tmp_path / "migration.csv")


# ---------------------------------------------------------------- linking

def technosphere_data() -> list[dict]:
    return [{"name": "Product (A)", "unit": "kilogram", "location": "CH", "database": "db", "code": "a",
             "exchanges": [{"name": "Product (A)", "unit": "kilogram", "location": "CH", "type": "production", "amount": 1},
                           {"name": " product b ", "unit": "Kilogram", "location": "ch", "type": "technosphere", "amount": 1},
                           {"name": "Product A", "unit": "kilogram", "location": "CH", "type": "technosphere", "amount": 1}]},
            {"name": "Product B", "unit": "kilogram", "location": "CH", "database": "db", "code": "b",
             "exchanges": [{"name": "Product B", "unit": "kilogram", "location": "CH", "type": "production", "amount": 1}]}]


def test_link_internally_is_case_insensitive_and_stripped():
    data = Linker().link_internally(technosphere_data())
    excs = data[0]["exchanges"]
    assert excs[0]["input"] == ("db", "a")
    assert excs[1]["input"] == ("db", "b")
    assert "input" not in excs[2]  # special characters are kept by default
    assert unlinked_summary(data) == {"technosphere": 1}


def test_link_internally_removing_special_characters():
    data = Linker(remove_special_characters=True).link_internally(technosphere_data())
    assert data[0]["exchanges"][2]["input"] == ("db", "a")


def test_linking_does_not_change_brightway_defaults():
    defaults = bw2io.utils.ExchangeLinker.parse_field.__defaults__
    Linker(remove_special_characters=False).link_internally(technosphere_data())
    assert bw2io.utils.ExchangeLinker.parse_field.__defaults__ == defaults


def test_unlink_selected_types():
    data = Linker().link_internally(technosphere_data())
    data = unlink(data, production=False, biosphere=False)
    assert data[0]["exchanges"][0]["input"] == ("db", "a")
    assert "input" not in data[0]["exchanges"][1]
