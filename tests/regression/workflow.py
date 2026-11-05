"""Run a standard import workflow with the old (function-based, v1) or the new (class-based) rosetta API
and dump the results to JSON, so both versions can be compared on real data.

Usage (see compare.py, which runs both and compares):

    python workflow.py --api new --data ../../data --out new.json
    PYTHONPATH=<folder containing rosetta_v1> python workflow.py --api old --data ../../data --out old.json

Input data (all optional, whatever exists is used):
    <data>/lcia/*.csv                       SimaPro LCIA method exports (required for the LCI part)
    <data>/lci/*.csv                        SimaPro LCI exports, one database per file, processed in name order;
                                            each database is linked to the databases processed before it
    <data>/lci/<stem>_migration.xlsx        optional exchange migration applied to database <stem>
    <data>/ecospold/datasets/               ecoinvent ecospold2 datasets (+ ../MasterData/ElementaryExchanges.xml)

Every run uses a fresh Brightway directory and a fresh UUID registry.
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile

BIOSPHERE = "biosphere - SimaPro"
UNLINKED = "biosphere - SimaPro - unlinked"
PROJECT = "rosetta regression"
MAX_LCA_ACTIVITIES = 25


def normalize(obj):
    """JSON-compatible, order-independent representation."""
    if isinstance(obj, dict):
        return {str(k): normalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [normalize(m) for m in obj]
    if isinstance(obj, float):
        return float("{:.12g}".format(obj))
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


def flow_identity(bw2data, key) -> object:
    """Replace keys of biosphere flows (random uuid4 codes) by the identity of the flow."""
    if key[0] in (BIOSPHERE, UNLINKED):
        flow = bw2data.get_activity(tuple(key))
        return [key[0], flow["name"], list(flow["categories"]), flow["unit"], flow["location"]]
    return list(key)


def dump_importer_data(data: list[dict]) -> list:
    """Importer data before writing; links to biosphere flows are dropped (codes are random), linked yes/no is kept."""
    out = []
    for ds in data:
        ds = dict(ds)
        excs = []
        for exc in ds.pop("exchanges", []):
            exc = dict(exc)
            if exc.get("type") == "biosphere" and "input" in exc:
                exc["input"] = ["<linked to {}>".format(exc["input"][0])]
            excs.append(normalize(exc))
        ds = normalize(ds)
        ds["exchanges"] = sorted(excs, key=lambda e: json.dumps(e, sort_keys=True))
        out.append(ds)
    return sorted(out, key=lambda d: (str(d.get("code")), json.dumps(d, sort_keys=True)))


def dump_database(bw2data, name: str) -> list:
    out = []
    for act in bw2data.Database(name):
        ds = dict(act.as_dict())
        ds.pop("id", None)
        if name in (BIOSPHERE, UNLINKED):
            ds.pop("code", None)
        excs = []
        for exc in act.exchanges():
            e = dict(exc.as_dict())
            e["input"] = flow_identity(bw2data, e["input"])
            e["output"] = flow_identity(bw2data, e["output"])
            excs.append(normalize(e))
        ds = normalize(ds)
        ds["exchanges"] = sorted(excs, key=lambda e: json.dumps(e, sort_keys=True))
        out.append(ds)
    return sorted(out, key=lambda d: json.dumps(d, sort_keys=True))


def dump_methods(bw2data, names) -> dict:
    out = {}
    for name in sorted(names, key=str):
        method = bw2data.Method(tuple(name))
        cfs = sorted(([flow_identity(bw2data, key), amount] for key, amount in method.load()), key=lambda m: json.dumps(m))
        out[" | ".join(name)] = {"metadata": normalize({k: v for k, v in method.metadata.items() if k not in ("abbreviation",)}),
                                 "cfs": normalize(cfs)}
    return out


def lca_scores(bw2data, bw2calc, databases: list[str], methods) -> dict:
    out = {}
    methods = sorted(methods, key=str)
    for db in databases:
        acts = sorted(bw2data.Database(db), key=lambda a: a.key)[:MAX_LCA_ACTIVITIES]
        for act in acts:
            for method in methods:
                try:
                    lca = bw2calc.LCA({act: 1}, method)
                    lca.lci()
                    lca.lcia()
                    out["{} | {}".format(act.key, " | ".join(method))] = float("{:.10g}".format(lca.score))
                except Exception as err:  # e.g. singular matrix: record the error type, it must match too
                    out["{} | {}".format(act.key, " | ".join(method))] = "ERROR " + type(err).__name__
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", choices=("old", "new"), required=True)
    parser.add_argument("--data", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    data_dir: pathlib.Path = args.data.resolve()

    workdir = pathlib.Path(tempfile.mkdtemp(prefix="rosetta_regression_{}_".format(args.api)))
    os.environ["ROSETTA_UUID_FILE"] = str(workdir / "UUIDs.xlsx")
    bw_dir = workdir / "brightway"
    bw_dir.mkdir()
    logs = workdir / "logs"
    logs.mkdir()

    import bw2calc
    import bw2data

    result: dict = {"api": args.api}
    lcia_files = sorted((data_dir / "lcia").glob("*.[cC][sS][vV]"))
    lci_files = sorted((data_dir / "lci").glob("*.[cC][sS][vV]"))
    written: list[str] = []

    if args.api == "old":
        from rosetta_v1 import link, utils
        from rosetta_v1.lci import import_SimaPro_LCI_inventories, migrate_from_excel_file
        from rosetta_v1.lcia import import_SimaPro_LCIA_methods, register_biosphere, register_SimaPro_LCIA_methods
        from functools import partial

        utils.change_brightway_project_directory(bw_dir)
        bw2data.projects.set_current(PROJECT)

        if lcia_files:
            methods = import_SimaPro_LCIA_methods(path_to_SimaPro_CSV_LCIA_files=data_dir / "lcia")
            result["lcia_import"] = normalize(sorted(methods, key=lambda m: str(m["name"])))
            register_biosphere(Brightway_project_name=PROJECT, BRIGHTWAY2_DIR=bw_dir,
                               biosphere_db_name=BIOSPHERE, imported_methods=methods)
            register_SimaPro_LCIA_methods(imported_methods=methods, biosphere_db_name=BIOSPHERE,
                                          Brightway_project_name=PROJECT, BRIGHTWAY2_DIR=bw_dir,
                                          logs_output_path=logs)

        for filepath in lci_files if lcia_files else []:
            name = filepath.stem
            db = import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths=[filepath], db_name=name)
            result["lci_import_" + name] = dump_importer_data(db.data)
            migration = filepath.parent / (name + "_migration.xlsx")
            if migration.exists():
                db.apply_strategy(partial(migrate_from_excel_file, excel_migration_filepath=migration,
                                          migrate_activities=False, migrate_exchanges=True))
            db.apply_strategy(partial(link.link_biosphere_flows_externally, biosphere_db_name=BIOSPHERE,
                                      biosphere_db_name_unlinked=UNLINKED, other_biosphere_databases=None,
                                      linking_order=None, relink=False, strip=True, case_insensitive=True,
                                      remove_special_characters=False))
            utils.add_unlinked_flows_to_biosphere_database(db=db, biosphere_db_name_unlinked=UNLINKED,
                                                           biosphere_db_name=BIOSPHERE)
            db.apply_strategy(partial(link.link_activities_internally, production_exchanges=True,
                                      substitution_exchanges=True, technosphere_exchanges=True, relink=False,
                                      strip=True, case_insensitive=True, remove_special_characters=False))
            if written:
                db.apply_strategy(partial(link.link_activities_externally, link_to_databases=tuple(written),
                                          link_production_exchanges=False, link_substitution_exchanges=True,
                                          link_technosphere_exchanges=True, relink=False, strip=True,
                                          case_insensitive=True, remove_special_characters=False))
            result["lci_linked_" + name] = dump_importer_data(db.data)
            result["unlinked_" + name] = normalize(utils.linking_summary_dictionary(db.data))
            if name in bw2data.databases:
                del bw2data.databases[name]
            db.write_database()
            written.append(name)

        ecospold = data_dir / "ecospold" / "datasets"
        if ecospold.exists():
            from rosetta_v1.lci import import_XML_LCI_inventories
            xml = import_XML_LCI_inventories(XML_LCI_filepath=ecospold, db_name="ecoinvent XML",
                                             biosphere_db_name="biosphere - XML",
                                             db_model_type_name="cutoff", db_process_type_name="unit")
            result["xml_import"] = dump_importer_data(xml.data)

    else:
        from rosetta import BrightwayProject, SimaProLCIAImporter, SimaProLCIImporter

        BrightwayProject(PROJECT, directory=bw_dir)

        if lcia_files:
            lcia = SimaProLCIAImporter(data_dir / "lcia")
            result["lcia_import"] = normalize(sorted(lcia.data, key=lambda m: str(m["name"])))
            lcia.write_biosphere(BIOSPHERE)
            lcia.write_methods(logs_dir=logs)

        for filepath in lci_files if lcia_files else []:
            name = filepath.stem
            db = SimaProLCIImporter(filepath, name, biosphere=BIOSPHERE, unlinked_biosphere=UNLINKED)
            result["lci_import_" + name] = dump_importer_data(db.data)
            migration = filepath.parent / (name + "_migration.xlsx")
            if migration.exists():
                db.migrate(migration)
            db.link_biosphere().add_unlinked_to_biosphere().link_internally()
            if written:
                db.link_to(*written, production=False)
            result["lci_linked_" + name] = dump_importer_data(db.data)
            result["unlinked_" + name] = normalize(db.unlinked_summary())
            db.write(overwrite=True)
            written.append(name)

        ecospold = data_dir / "ecospold" / "datasets"
        if ecospold.exists():
            from rosetta import EcospoldLCIImporter
            xml = EcospoldLCIImporter(ecospold, "ecoinvent XML", biosphere="biosphere - XML",
                                      model_type="cutoff", process_type="unit")
            result["xml_import"] = dump_importer_data(xml.data)

    if BIOSPHERE in bw2data.databases:
        result["db_" + BIOSPHERE] = dump_database(bw2data, BIOSPHERE)
    if UNLINKED in bw2data.databases:
        result["db_" + UNLINKED] = dump_database(bw2data, UNLINKED)
    for name in written:
        result["db_" + name] = dump_database(bw2data, name)
    result["methods"] = dump_methods(bw2data, list(bw2data.methods))
    result["lca_scores"] = lca_scores(bw2data, bw2calc, written, list(bw2data.methods))

    args.out.write_text(json.dumps(result, indent=1, sort_keys=True))
    print("Wrote", args.out, "| sections:", ", ".join(k for k in result if k != "api"), file=sys.stderr)


if __name__ == "__main__":
    main()
