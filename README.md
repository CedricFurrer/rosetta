# rosetta
rosetta is a Python package to work with SimaPro data in Brightway (v2): import and standardize SimaPro (and ecoinvent ecospold2) inventories and LCIA methods, link and migrate them, harmonize them between databases, calculate LCA results and export inventories back to SimaPro.

## Installation
The Brightway2 / PyTorch stack is easiest to install with conda, then rosetta itself with pip:

```bash
conda env create -f environment_macos.yml   # or: bw2_ab_environment.yml on Linux
conda activate rosetta
pip install -e .                            # editable install from the repository root
```

## Quick start

```python
from rosetta import BrightwayProject, SimaProLCIAImporter, SimaProLCIImporter

project = BrightwayProject("my project", directory="Brightway2_projects")

# LCIA methods and the biosphere they define
lcia = SimaProLCIAImporter("data/lcia")                # a CSV file, a folder of CSV files or a list of files
lcia.write_biosphere("biosphere3 - from SimaPro")
lcia.write_methods()

# Inventories
db = SimaProLCIImporter("data/lci/ECO.CSV", "ecoinvent v3.11 - SimaPro",
                        biosphere="biosphere3 - from SimaPro",
                        unlinked_biosphere="biosphere3 - from SimaPro - unlinked")
db.migrate("data/lci/custom_migration_ECO.xlsx")       # optional exchange migration (Excel or JSON)
db.link_biosphere()                                    # link to the biosphere (and the unlinked biosphere)
db.add_unlinked_to_biosphere()                         # register remaining flows in the unlinked biosphere
db.link_internally()
db.statistics()
db.write(overwrite=True)

# A second database that uses the first one as background
wfldb = SimaProLCIImporter("data/lci/WFLDB.CSV", "WFLDB", biosphere="biosphere3 - from SimaPro",
                           unlinked_biosphere="biosphere3 - from SimaPro - unlinked")
wfldb.link_biosphere().add_unlinked_to_biosphere().link_internally().link_to("ecoinvent v3.11 - SimaPro", production=False)
wfldb.write(overwrite=True)
```

All processing methods of the importers modify the importer in place and return it, so they can be chained.

## Package overview

| Class / module | Purpose |
|---|---|
| `BrightwayProject` ([project.py](src/rosetta/project.py)) | Select the Brightway projects directory and project; delete/copy databases; export an overview of biosphere flows and methods |
| `SimaProLCIImporter`, `EcospoldLCIImporter` ([importers](src/rosetta/importers)) | Import inventories from SimaPro CSV or ecoinvent ecospold2 (XML) and apply the standardization strategies |
| `LCIImporter` ([importers/base.py](src/rosetta/importers/base.py)) | Base class of the importers: `migrate`, `link_biosphere`, `link_internally`, `link_to`, `unlink`, `select`, `rename`, `extend`, `add_unlinked_to_biosphere`, `write`, `from_brightway` |
| `SimaProLCIAImporter`, `EcoinventLCIAImporter` ([importers](src/rosetta/importers)) | Import LCIA methods from SimaPro CSV or the ecoinvent LCIA Excel file; write the biosphere and the methods |
| `Linker` ([linking.py](src/rosetta/linking.py)) | Linking of exchanges (internally, to other databases, to biosphere databases) |
| `Migration` ([migration.py](src/rosetta/migration.py)) | Field/amount migrations of activities and exchanges, from Excel or JSON |
| [strategies](src/rosetta/strategies) | The individual standardization steps (functions `data -> data`), usable with `importer.apply(strategy, **kwargs)` |
| [methods.py](src/rosetta/methods.py) | Post-processing of registered LCIA methods (`add_excluded_longterm_method`, `add_damage_normalization_weighting`, ...) |
| `Inventory`, `Exchange`, `Uncertainty` ([builder.py](src/rosetta/builder.py)) | Build standardized inventories and exchanges to register in Brightway |
| `LCACalculation` ([calculation.py](src/rosetta/calculation.py)) | LCA scores, process and emission contributions, characterization factors, LCI exchanges |
| `SimaProCSVExporter` ([exporter.py](src/rosetta/exporter.py)) | Export registered activities back to SimaPro CSV (only for data imported with rosetta) |
| [harmonization](src/rosetta/harmonization) | `ActivityHarmonization`, `BiosphereHarmonization`, `Correspondence` (ecoinvent version correspondence files) and SBERT-based flow mapping |

Check out the [notebook folder](notebook/) for complete use cases. Input data (SimaPro exports, ecoinvent correspondence files) goes into `data/lci`, `data/lcia` and `data/correspondence`.

`SimaProLCIImporter` registers the codes it generates in `UUIDs.xlsx` inside the package. Set the environment variable `ROSETTA_UUID_FILE` to store it elsewhere.

## Migrating from version 1
Version 2 replaces the function-based API with the classes above. The processing steps themselves are unchanged.

| Version 1 | Version 2 |
|---|---|
| `change_brightway_project_directory(dir)` + `bw2data.projects.set_current(name)` | `BrightwayProject(name, directory=dir)` |
| `import_SimaPro_LCI_inventories([path], db_name)` | `SimaProLCIImporter(path, db_name)` |
| `import_XML_LCI_inventories(path, db_name, bio, model, process)` | `EcospoldLCIImporter(path, db_name, biosphere=bio, model_type=model, process_type=process)` |
| `import_SimaPro_LCIA_methods(folder)` + `register_biosphere(...)` + `register_SimaPro_LCIA_methods(...)` | `lcia = SimaProLCIAImporter(folder)`; `lcia.write_biosphere(bio)`; `lcia.write_methods()` |
| `import_XML_LCIA_methods(path, bio)` + `register_XML_LCIA_methods(methods)` | `EcoinventLCIAImporter(path, bio).write_methods()` |
| `db.apply_strategy(partial(link.link_biosphere_flows_externally, biosphere_db_name=bio, biosphere_db_name_unlinked=unlinked, ...))` | `db.link_biosphere(bio, unlinked)` |
| `db.apply_strategy(partial(link.link_activities_internally, ...))` | `db.link_internally(...)` |
| `db.apply_strategy(partial(link.link_activities_externally, link_to_databases=(a, b), ...))` | `db.link_to(a, b, ...)` |
| `db.apply_strategy(partial(link.remove_linking, ...))` | `db.unlink(...)` |
| `db.apply_strategy(partial(migrate_from_excel_file, excel_migration_filepath=f, ...))` | `db.migrate(f, ...)` (also for JSON files) |
| `db.apply_strategy(partial(change_database_name, new_db_name=n))` | `db.rename(n)` |
| `select_inventory_using_regex(...)` into a new `LCIImporter` | `db.select(patterns, exclude=..., db_name=...)` |
| `utils.add_unlinked_flows_to_biosphere_database(db, unlinked, bio)` | `db.add_unlinked_to_biosphere(unlinked, bio)` |
| `utils.copy_brightway_database(a, b)` | `LCIImporter.from_brightway(a, new_name=b)` |
| `del bw2data.databases[n]`; `db.write_database()` | `db.write(overwrite=True)` |
| `write_biosphere_flows_and_method_names_to_XLSX(bio, out)` | `project.export_overview(bio, out)` |
| `create_base_inventory(...)`, `create_base_exchange(...)`, `create_base_exchange_from_existing_inventory(...)` | `Inventory(...).to_dict()`, `Exchange(...).to_dict()`, `Exchange.from_activity(...)` |
| `export_SimaPro_CSV(activities, folder, name)` | `SimaProCSVExporter().export(activities, folder, name)` |
| `LCA_Calculation` | `LCACalculation` |
| `rosetta.correspondence.correspondence.Correspondence`, `rosetta.activity_harmonization.*` | `rosetta.harmonization.*` |

The `case_insensitive` and `strip` arguments of the old linking functions are gone: they never had an effect, because Brightway's linker always matches case-insensitively on stripped values. Linking also no longer changes Brightway's global `ExchangeLinker` settings.

## Tests
```bash
pip install -e ".[dev]"
pytest
```

The tests run the full SimaPro workflow on small synthetic exports in `tests/fixtures/simapro`. [tests/regression](tests/regression) contains a script that runs the same workflow with version 1 and version 2 on your own data and compares the imported data, written databases, LCIA methods and LCA scores.

## Dependencies
rosetta depends on Brightway v2 (it is not yet compatible with Brightway 2.5) and works with:
- bw2io → _v0.8.12_
- bw2data → _v3.6.6_
- bw2calc → _v1.8.2_
- bw2analyzer → _v0.10_
- sentence-transformers → _v2.7.0_
