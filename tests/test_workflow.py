"""End-to-end SimaPro workflow on the synthetic fixtures (tests/fixtures/simapro)."""

import bw2calc
import bw2data
import pytest

from conftest import BIOSPHERE, UNLINKED

CLIMATE = ("Test method", "Climate change")


def farm_activity(name_start: str):
    return next(a for a in bw2data.Database("farm") if a["name"].startswith(name_start))


def test_lcia_methods_and_biosphere(written_databases):
    lcia = written_databases["lcia"]
    assert sorted(lcia.method_names) == [("Test method", "Acidification"), ("Test method", "Climate change"), ("Test method", "Resources")]
    assert set(lcia.method_names) <= set(bw2data.methods)
    assert len(bw2data.Database(BIOSPHERE)) == 9
    assert bw2data.config.p["biosphere_database"] == BIOSPHERE


def test_multi_output_process_is_allocated(written_databases):
    grain, straw = farm_activity("Wheat grain"), farm_activity("Wheat straw")
    assert grain["allocation"] == pytest.approx(0.9)
    assert straw["allocation"] == pytest.approx(0.1)
    assert grain["output amount"] == pytest.approx(8)
    assert grain["location"] == "CH"
    assert grain["name"] == "Wheat grain, at farm/{COUNTRY} U"


def test_everything_linked(written_databases):
    for importer in (written_databases["background"], written_databases["farm"]):
        assert importer.unlinked_summary() == {}
        assert importer.all_linked


def test_unlinked_biosphere_collects_uncharacterized_flows(written_databases):
    names = sorted(flow["name"] for flow in bw2data.Database(UNLINKED))
    assert names == ["Cadmium", "Nitrate", "Occupation, arable land", "Sulfur dioxide", "Water, river"]


def test_migration_applied(written_databases):
    biosphere_inputs = [exc.input["name"] for exc in farm_activity("Wheat grain").biosphere()]
    assert "Methane, biogenic" in biosphere_inputs
    assert "Methane" not in biosphere_inputs


def test_cross_database_links(written_databases):
    inputs = {exc.input.key[0] for exc in farm_activity("Wheat grain").technosphere()}
    assert inputs == {"background"}


def test_lca_score(written_databases):
    lca = bw2calc.LCA({farm_activity("Wheat grain"): 1}, CLIMATE)
    lca.lci()
    lca.lcia()
    # (0.003*27 + 0.002*273 + 0.4*(0.02 + 0.001*28 + 0.01*0.1) + 1.5*0.1 - 0.5*0.1) * 0.9 / 8
    assert lca.score == pytest.approx(0.0839925, rel=1e-6)


def test_lca_calculation_class(written_databases):
    from rosetta import LCACalculation

    calc = LCACalculation(activities=[farm_activity("Wheat grain")], methods=[CLIMATE], print_progress_bar=False)
    calc.calculate()
    results = calc.get_results()
    assert results


def test_write_refuses_to_overwrite(written_databases):
    with pytest.raises(ValueError, match="already exists"):
        written_databases["farm"].write()


def test_select_and_rename(written_databases):
    farm = written_databases["farm"]
    straw = farm.select(["straw"], db_name="straw only")
    assert len(straw) == 1 and straw.db_name == "straw only"
    assert all(ds["database"] == "straw only" for ds in straw.data)
    assert len(farm) == 2  # the original is unchanged


def test_from_brightway_roundtrip(written_databases):
    from rosetta import LCIImporter

    copied = LCIImporter.from_brightway("farm", new_name="farm copy")
    assert len(copied) == 2
    assert {ds["database"] for ds in copied.data} == {"farm copy"}


def test_export_to_simapro_csv(written_databases, tmp_path):
    from rosetta import SimaProCSVExporter

    exporter = SimaProCSVExporter()
    filepath = exporter.export([farm_activity("Wheat grain")], folder=tmp_path, filename="export", timestamp=False)
    content = filepath.read_text(encoding="utf-8")
    assert filepath.name == "export.csv"
    assert content.startswith("{CSV separator: Tab}")
    assert "Wheat grain, at farm/CH U" in content


def test_project_overview(written_databases, brightway_project, tmp_path):
    brightway_project.export_overview(BIOSPHERE, tmp_path)
    assert (tmp_path / "Biosphere_elementary_flows.xlsx").exists()
    assert (tmp_path / "Available_LCIA_method_names.xlsx").exists()
    metadata = brightway_project.activity_metadata("farm")
    assert {m["activity_name"] for m in metadata} == {"Wheat grain, at farm/{COUNTRY} U", "Wheat straw, at farm/{COUNTRY} U"}
