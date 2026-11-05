import pathlib
here: pathlib.Path = pathlib.Path(__file__).parent

if __name__ == "__main__":
    import os
    os.chdir(here.parent)

import copy
import json
from rosetta import utils
import bw2io
import bw2data
from rosetta import link
import datetime
import pandas as pd
from ast import literal_eval
from functools import partial
from rosetta.lcia import (import_SimaPro_LCIA_methods,
                  import_XML_LCIA_methods,
                  register_biosphere,
                  register_SimaPro_LCIA_methods,
                  register_XML_LCIA_methods,
                  # add_damage_normalization_weighting,
                  write_biosphere_flows_and_method_names_to_XLSX)

from rosetta.lci import (unregionalize_biosphere,
                 import_SimaPro_LCI_inventories,
                 import_XML_LCI_inventories,
                 migrate_from_excel_file,
                 migrate_from_json_file,
                 create_XML_biosphere_from_elmentary_exchanges_file,
                 create_XML_biosphere_from_LCI,
                 select_inventory_using_regex)

from rosetta.harmonization import (create_harmonized_biosphere_migration,
                           elementary_flows_that_are_not_used_in_XML_methods)

from rosetta.activity_harmonization import (ActivityHarmonization,
                                    ActivityDefinition)

from rosetta.correspondence.correspondence import Correspondence

from rosetta.utils import (change_brightway_project_directory,
                   change_database_name)
from rosetta.calculation import LCA_Calculation
from rosetta import helper as hp

#%% File- and folderpaths, key variables

# LCI and LCIA data
LCI_ecoinvent_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "ECO_fromSimaPro"
LCI_ecoinvent_xml_folderpath: pathlib.Path = here.parent / "data" / "lci" / "ECO_fromXML"
LCI_ecoinvent_xml_data_folderpath_temp: pathlib.Path = LCI_ecoinvent_xml_folderpath / "ecoinvent 3.11_cutoff_ecoSpold02"
LCI_ecoinvent_xml_data_folderpath: pathlib.Path = LCI_ecoinvent_xml_folderpath / "ecoinvent 3.11_cutoff_ecoSpold02"
LCI_ecoinvent_xml_datasets_folderpath_temp: pathlib.Path = LCI_ecoinvent_xml_data_folderpath_temp / "datasets"
LCI_ecoinvent_xml_datasets_folderpath: pathlib.Path = LCI_ecoinvent_xml_data_folderpath / "datasets"
LCI_agribalyse_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "AGB_fromSimaPro"
LCI_agrifootprint_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "AGF_fromSimaPro"
LCI_wfldb_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "WFLDB_fromSimaPro"
LCI_salca_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "SALCA_fromSimaPro"
LCIA_SimaPro_CSV_folderpath: pathlib.Path = here.parent / "data" / "lcia" / "fromSimaPro"
LCIA_XML_folderpath_temp: pathlib.Path = here.parent / "data" / "lcia" / "fromXML" / "ecoinvent 3.11_LCIA_implementation"
LCIA_XML_folderpath: pathlib.Path = here.parent / "data" / "lcia" / "fromXML" / "ecoinvent 3.11_LCIA_implementation"
LCIA_XML_filename_temp: str = "LCIA Implementation 3.11.xlsx"
LCIA_XML_filename: str = "LCIA Implementation 3.11.xlsx"
LCIA_XML_filepath_temp: pathlib.Path = LCIA_XML_folderpath_temp / LCIA_XML_filename_temp
LCIA_XML_filepath: pathlib.Path = LCIA_XML_folderpath / LCIA_XML_filename
LCIA_XML_sheetname: str = "CFs"
LCIA_XML_elementary_exchanges_filename: str = "ElementaryExchanges.xml"
LCIA_XML_elementary_exchanges_filepath_temp: pathlib.Path = LCI_ecoinvent_xml_data_folderpath_temp / "MasterData" / LCIA_XML_elementary_exchanges_filename
LCIA_XML_elementary_exchanges_filepath: pathlib.Path = LCI_ecoinvent_xml_data_folderpath / "MasterData" / LCIA_XML_elementary_exchanges_filename

# Generic and Brightway
if bw2data.__version__[0] >= 4:
    project_path: pathlib.Path = here.parent.parent  / "Brightway2.5_projects"
else:
    project_path: pathlib.Path = here.parent.parent / "Brightway2_projects"

start_time: datetime.datetime = datetime.datetime.now()
project_path.mkdir(exist_ok = True)
project_name: str = "Brightway paper v2.4"
# project_name: str = "test"

# Correspondence files
folderpath_correspondence_files: pathlib.Path = here.parent / "data" / "correspondence"

#%% Change brightway project directory and setup project
change_brightway_project_directory(project_path)

# If project already exists, raise error
if project_name in bw2data.projects:
    raise ValueError("Project '{}' already exists and does not need any setup.".format(project_name))
    bw2data.projects.delete_project(name = project_name, delete_dir = True)
    # bw2data.projects.delete_project(name = "test111", delete_dir = True)
    # bw2data.projects.rename_project("Brightway paper")

# Set project
bw2data.projects.set_current(project_name)
# print(bw2data.databases)
# del bw2data.databases["AgriFootprint v7.0.1 - SimaPro - unregionalized (XML background ecoinvent v3.12)"]

#%% File- and folderpaths

# Setup output path
output_path: pathlib.Path = pathlib.Path(bw2data.projects.output_dir)

# Migration
filename_biosphere_migration_data: str = "biosphere_migration.json"
filepath_biosphere_migration_data: pathlib.Path = output_path / filename_biosphere_migration_data
filepath_AGB_background_ei_migration_data: pathlib.Path = output_path / "AGB_background_ei_migration_data.json"
filepath_WFLDB_background_ei_migration_data: pathlib.Path = output_path / "WFLDB_background_ei_migration_data.json"
filepath_SALCA_background_ei_migration_data: pathlib.Path = output_path / "SALCA_background_ei_migration_data.json"
filepath_AGF_background_ei_migration_data: pathlib.Path = output_path / "AGF_background_ei_migration_data.json"

# Logs
filename_biosphere_flows_not_specified_in_XML_methods: str = "biosphere_flows_not_specified_in_LCIA_methods_from_XML.xlsx"

# Other
filename_SBERT_biosphere_names_validated: str = "manually_checked_SBERT_biosphere_names_corrected_v2.xlsx"
filename_agribalyse_custom_mapping_harmonization: str = "custom_mapping_harmonization_AGB_v311.xlsx"
filename_wfldb_custom_mapping_harmonization: str = "custom_mapping_harmonization_WFLDB_v311.xlsx"
filename_salca_custom_mapping_harmonization: str = "custom_mapping_harmonization_SALCA_v311.xlsx"
filename_agrifootprint_custom_mapping_harmonization: str = "custom_mapping_harmonization_AGF_v311.xlsx"

#%% Defaults for key variables
biosphere_db_name_simapro: str = "biosphere3 - from SimaPro"
biosphere_db_name_xml: str = "biosphere3 - from XML"
unlinked_biosphere_db_name: str = biosphere_db_name_simapro + " - unlinked"

ecoinvent_db_name_simapro: str = "ecoinvent v3.11 Cut-off - SimaPro - regionalized"
ecoinvent_db_name_simapro_unreg: str = "ecoinvent v3.11 Cut-off - SimaPro - unregionalized"
ecoinvent_db_name_xml: str = "ecoinvent v3.11 Cut-off - XML - unregionalized"
ecoinvent_db_name_xml_migrated: str = "ecoinvent v3.11 Cut-off - XML - unregionalized (migrated to SimaPro biosphere)"

agribalyse_db_name_simapro: str = "Agribalyse v3.2 - SimaPro - unregionalized (SimaPro background ecoinvent v3.9.1)"
agribalyse_db_name_updated_simapro: str = "Agribalyse v3.2 - SimaPro  - unregionalized (XML background ecoinvent v3.11)"

agrifootprint_db_name_simapro: str = "AgriFootprint v7.0.1 - SimaPro - unregionalized (SimaPro background ecoinvent v3.10.1)"
agrifootprint_db_name_updated_simapro: str = "AgriFootprint v7.0.1 - SimaPro - unregionalized (XML background ecoinvent v3.11)"

wfldb_db_name_simapro: str = "World Food LCA Database v3.5 - SimaPro - unregionalized (SimaPro background ecoinvent v3.5)"
wfldb_db_name_updated_simapro: str = "World Food LCA Database v3.5 - SimaPro - unregionalized (XML background ecoinvent v3.11)"

salca_db_name_simapro: str = "SALCA Database v3.11 - SimaPro - unregionalized (SimaPro background ecoinvent v3.11)"
salca_db_name_updated_simapro: str = "SALCA Database v3.11 - SimaPro - unregionalized (XML background ecoinvent v3.11)"

#%% Import SimaPro LCIA methods and create SimaPro biosphere database
methods: list[dict] = import_SimaPro_LCIA_methods(path_to_SimaPro_CSV_LCIA_files = LCIA_SimaPro_CSV_folderpath,
                                                  encoding = "latin-1",
                                                  delimiter = "\t",
                                                  verbose = True)

# Delete biosphere database if already existing
if biosphere_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + biosphere_db_name_simapro)
    del bw2data.databases[biosphere_db_name_simapro]

register_biosphere(Brightway_project_name = project_name,
                   BRIGHTWAY2_DIR = project_path,
                   biosphere_db_name = biosphere_db_name_simapro,
                   imported_methods = methods,
                   verbose = True)

register_SimaPro_LCIA_methods(imported_methods = methods,
                              biosphere_db_name = biosphere_db_name_simapro,
                              Brightway_project_name = project_name,
                              BRIGHTWAY2_DIR = project_path,
                              logs_output_path = output_path,
                              verbose = True)

# add_damage_normalization_weighting(original_method = ("SALCA v2.01", "CEENE - Fossil fuels"),
#                                    normalization_factor = 2,
#                                    weighting_factor = None,
#                                    damage_factor = None,
#                                    new_method = ("SALCA v2.01", "CEENE - Fossil fuels", "normalized"),
#                                    new_method_unit = "MJeq",
#                                    new_method_description = "added a normalization factor of 2 to the original method",
#                                    verbose = True)

write_biosphere_flows_and_method_names_to_XLSX(biosphere_db_name = biosphere_db_name_simapro,
                                               output_path = output_path,
                                               verbose = True)

# Free up memory
del methods


#%% Custom function to extract the LCI exchanges from a LCI importer object
def extract_LCI_exchanges(acts: list, db_name: str):
    import bw2calc
    import numpy as np
    
    act_db, _ = acts[0].key
    lca_object = bw2calc.LCA({acts[0].key: 1}, method = list(bw2data.methods)[0])
    lca_object.lci()
    lca_object.lcia()
    
    biosphere_keys = np.array([str(m) for m in lca_object.biosphere_dict.keys()], dtype = "U")
    
    conversions: dict[str, dict[str, float]] = {"kilogram": 1,
                                                "kilowatt hour": 1/3.6,
                                                "megajoule": 1,
                                                "kilometer": 0.001,
                                                "meter": 1,
                                                "kilometer-year": 0.001,
                                                "meter-year": 1,
                                                "square meter-year": 1,
                                                "cubic meter-year": 1,
                                                "guest night": 1,
                                                "guestnight": 1,
                                                "unit": 1,
                                                "hour": 1/60,
                                                "minutes": 1,
                                                "hectare": 0.0001,
                                                "square meter": 1,
                                                "cubic meter": 0.001,
                                                "litre": 1,
                                                "person kilometer": 1,
                                                "ton kilometer": 1,
                                                "kilogram day": 1
                                                }

    # Pre-allocate result arrays
    emission_contribution = {}
    
    for act in hp.progressbar(acts):
        conv_factor = conversions[act["unit"]]
        lca_object.redo_lci({act: 1 * conv_factor})
        
        # Extract non-zero inventory values
        inventory_sum = np.array(lca_object.inventory.sum(axis=1))[:, 0]
        mask = inventory_sum != 0
        
        # Only process non-zero entries
        n_nonzero = mask.sum()
        if n_nonzero > 0:
            
            for i in np.where(mask)[0]:
                bio_id: tuple = literal_eval(str(biosphere_keys[i]))
                emission = inventory_sum[i]
                
                if bio_id not in emission_contribution:
                    emission_contribution[bio_id]: list[int, float] = [0, float(0)]
                
                emission_contribution[bio_id][0] += 1
                emission_contribution[bio_id][1] += emission

    emission_contribution_list: list[dict] = [{"Activity_database": act_db,
                                               "Flow_database": flow_db,
                                               "Flow_code": flow_code,
                                               "Number_of_activities_that_use_this_flow": n,
                                               "Database_emission_sum": emission_sum
                                               } for (flow_db, flow_code), (n, emission_sum) in emission_contribution.items()]
    
    df: pd.DataFrame = pd.DataFrame(emission_contribution_list)
    return df


#%% Import the original ecoinvent database extract from SimaPro
original_ecoinvent_db_simapro: bw2io.importers.base_lci.LCIImporter = import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths = [LCI_ecoinvent_simapro_folderpath / "ECO.CSV"],
                                                                                                     db_name = ecoinvent_db_name_simapro,
                                                                                                     encoding = "latin-1",
                                                                                                     delimiter = "\t",
                                                                                                     verbose = True)

original_ecoinvent_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                                     excel_migration_filepath = LCI_ecoinvent_simapro_folderpath / "custom_migration_ECO.xlsx",
                                                     migrate_activities = False,
                                                     migrate_exchanges = True),
                                             verbose = True)

# Remove linking
original_ecoinvent_db_simapro.apply_strategy(partial(link.remove_linking,
                                                     production_exchanges = True,
                                                     substitution_exchanges = True,
                                                     technosphere_exchanges = True,
                                                     biosphere_exchanges = True))

print("\n------- Statistics")
original_ecoinvent_db_simapro.statistics()


#%% Patterns to identify inventories from different databases

# Specific patterns that are used to identify SALCA inventories
SALCA_patterns: list[str] = ["SALCA"]

# Specific patterns that are used to identify WFLDB inventories
WFLDB_patterns: list[str] = ["WFLDB", # because why not finding WFLDB inventories in SALCA/ecoinvent?
                             "Diesel combustion, in tractor/kg/", # Specific SALCA inventory that we need since it is internally referred to
                             "Shed, large, wood, non-insulated, fire-unprotected, at farm/m2/" # Specific SALCA inventory that we need since it is internally referred to
                             ]

#%% Import regionalized ecoinvent LCI database from SimaPro
ecoinvent_db_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(ecoinvent_db_name_simapro)
ecoinvent_db_simapro.data: list[dict] = select_inventory_using_regex(db_var = copy.deepcopy(original_ecoinvent_db_simapro.data),
                                                                     exclude = True,
                                                                     include = False,
                                                                     patterns = SALCA_patterns + WFLDB_patterns,
                                                                     case_sensitive = True)
ecoinvent_db_simapro.apply_strategy(partial(change_database_name,
                                            new_db_name = ecoinvent_db_name_simapro,
                                            ))         

ecoinvent_db_simapro.apply_strategy(partial(link.link_activities_internally,
                                            production_exchanges = True,
                                            substitution_exchanges = True,
                                            technosphere_exchanges = True,
                                            relink = False,
                                            strip = True,
                                            case_insensitive = True,
                                            remove_special_characters = False,
                                            verbose = True), verbose = True)    

# Link biosphere flows
ecoinvent_db_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                            biosphere_db_name = biosphere_db_name_simapro,
                                            biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                            other_biosphere_databases = None,
                                            linking_order = None,
                                            relink = False,
                                            strip = True,
                                            case_insensitive = True,
                                            remove_special_characters = False,
                                            verbose = True), verbose = True)

print("\n------- Statistics")
ecoinvent_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = ecoinvent_db_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)

# Delete ecoinvent database if already existing
if ecoinvent_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + ecoinvent_db_name_simapro)
    del bw2data.databases[ecoinvent_db_name_simapro]

# Write database
print("\n------- Write database: " + ecoinvent_db_name_simapro)
ecoinvent_db_simapro.write_database()


#%% Import unregionalized ecoinvent LCI database from SimaPro
ecoinvent_db_simapro_unreg: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(ecoinvent_db_name_simapro_unreg)
ecoinvent_db_simapro_unreg.data = copy.deepcopy(ecoinvent_db_simapro.data)
ecoinvent_db_simapro_unreg.apply_strategy(partial(change_database_name,
                                                  new_db_name = ecoinvent_db_name_simapro_unreg,
                                                  ))
ecoinvent_db_simapro_unreg.apply_strategy(unregionalize_biosphere)

ecoinvent_db_simapro_unreg.apply_strategy(partial(link.remove_linking,
                                                  production_exchanges = True,
                                                  substitution_exchanges = True,
                                                  technosphere_exchanges = True,
                                                  biosphere_exchanges = True))

ecoinvent_db_simapro_unreg.apply_strategy(partial(link.link_activities_internally,
                                                  production_exchanges = True,
                                                  substitution_exchanges = True,
                                                  technosphere_exchanges = True,
                                                  relink = False,
                                                  strip = True,
                                                  case_insensitive = True,
                                                  remove_special_characters = False,
                                                  verbose = True), verbose = True)    

ecoinvent_db_simapro_unreg.apply_strategy(partial(link.link_biosphere_flows_externally,
                                                  biosphere_db_name = biosphere_db_name_simapro,
                                                  biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                                  other_biosphere_databases = None,
                                                  linking_order = None,
                                                  relink = False,
                                                  strip = True,
                                                  case_insensitive = True,
                                                  remove_special_characters = False,
                                                  verbose = True), verbose = True)

print("\n------- Statistics")
ecoinvent_db_simapro_unreg.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = ecoinvent_db_simapro_unreg,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)

# Delete ecoinvent database if already existing
if ecoinvent_db_name_simapro_unreg in bw2data.databases:
    print("\n------- Delete database: " + ecoinvent_db_name_simapro_unreg)
    del bw2data.databases[ecoinvent_db_name_simapro_unreg]

# Write database
print("\n------- Write database: " + ecoinvent_db_name_simapro_unreg)
ecoinvent_db_simapro_unreg.write_database()


#%% Import WFLDB LCI database from SimaPro
wfldb_db_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(wfldb_db_name_simapro)
wfldb_db_simapro.data: list[dict] = select_inventory_using_regex(db_var = copy.deepcopy(original_ecoinvent_db_simapro.data),
                                                                 exclude = False,
                                                                 include = True,
                                                                 patterns = WFLDB_patterns,
                                                                 case_sensitive = True)

wfldb_db_simapro.data += import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths = [LCI_wfldb_simapro_folderpath / "WFLDB.CSV"],
                                                        db_name = wfldb_db_name_simapro,
                                                        encoding = "latin-1",
                                                        delimiter = "\t",
                                                        verbose = True)

wfldb_db_simapro.apply_strategy(partial(change_database_name,
                                        new_db_name = wfldb_db_name_simapro,
                                        ))

wfldb_db_simapro.apply_strategy(unregionalize_biosphere)

wfldb_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                        excel_migration_filepath = LCI_wfldb_simapro_folderpath / "custom_migration_WFLDB.xlsx",
                                        migrate_activities = False,
                                        migrate_exchanges = True),
                                verbose = True)

wfldb_db_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                        biosphere_db_name = biosphere_db_name_simapro,
                                        biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                        other_biosphere_databases = None,
                                        linking_order = None,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

wfldb_db_simapro.apply_strategy(partial(link.link_activities_internally,
                                        production_exchanges = True,
                                        substitution_exchanges = True,
                                        technosphere_exchanges = True,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

wfldb_db_simapro.apply_strategy(partial(link.link_activities_externally,
                                        link_to_databases = (ecoinvent_db_name_simapro_unreg,),
                                        link_production_exchanges = False,
                                        link_substitution_exchanges = False,
                                        link_technosphere_exchanges = True,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

print("\n------- Statistics")
wfldb_db_simapro.statistics()

# wfldb_db_simapro.write_excel(only_unlinked = True)
# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = wfldb_db_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)
print("\n------- Statistics")
wfldb_db_simapro.statistics()

# Delete wfldb database if already existing
if wfldb_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + wfldb_db_name_simapro)
    del bw2data.databases[wfldb_db_name_simapro]

# Write database
print("\n------- Write database: " + wfldb_db_name_simapro)
wfldb_db_simapro.write_database()

# # Create a database object that will be used afterwards to update the background
# wfldb_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(wfldb_db_name_updated_simapro)
# wfldb_db_updated_simapro.data: list[dict] = copy.deepcopy(wfldb_db_simapro.data)

# # Rename the database with the new name
# wfldb_db_updated_simapro.apply_strategy(partial(change_database_name,
#                                                 new_db_name = wfldb_db_name_updated_simapro,
#                                                 ))

# Free up memory
del wfldb_db_simapro

#%% Import SALCA LCI database from SimaPro
salca_db_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(salca_db_name_simapro)
salca_db_simapro.data: list[dict] = select_inventory_using_regex(db_var = copy.deepcopy(original_ecoinvent_db_simapro.data),
                                                                 exclude = False,
                                                                 include = True,
                                                                 patterns = SALCA_patterns,
                                                                 case_sensitive = True)
salca_db_simapro.apply_strategy(partial(change_database_name,
                                        new_db_name = salca_db_name_simapro,
                                        ))

salca_db_simapro.apply_strategy(unregionalize_biosphere)

salca_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                        excel_migration_filepath = LCI_salca_simapro_folderpath / "custom_migration_SALCA.xlsx",
                                        migrate_activities = False,
                                        migrate_exchanges = True),
                                verbose = True)

salca_db_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                        biosphere_db_name = biosphere_db_name_simapro,
                                        biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                        other_biosphere_databases = None,
                                        linking_order = None,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

salca_db_simapro.apply_strategy(partial(link.link_activities_internally,
                                        production_exchanges = True,
                                        substitution_exchanges = True,
                                        technosphere_exchanges = True,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True) 

salca_db_simapro.apply_strategy(partial(link.link_activities_externally,
                                        link_to_databases = (ecoinvent_db_name_simapro_unreg, wfldb_db_name_simapro),
                                        link_production_exchanges = False,
                                        link_substitution_exchanges = False,
                                        link_technosphere_exchanges = True,
                                        relink = False,
                                        strip = True,
                                        case_insensitive = True,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

print("\n------- Statistics")
salca_db_simapro.statistics()
# salca_db_simapro.write_excel(only_unlinked = True)

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = salca_db_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)

# Delete ecoinvent database if already existing
if salca_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + salca_db_name_simapro)
    del bw2data.databases[salca_db_name_simapro]

# Write database
print("\n------- Write database: " + salca_db_name_simapro)
salca_db_simapro.write_database()

# # Create a database object that will be used afterwards to update the background
# salca_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(salca_db_name_updated_simapro)
# salca_db_updated_simapro.data: list[dict] = copy.deepcopy(salca_db_simapro.data)

# # Rename the database with the new name
# salca_db_updated_simapro.apply_strategy(partial(change_database_name,
#                                                 new_db_name = salca_db_name_updated_simapro,
#                                                 ))

# Free up memory
del salca_db_simapro


#%% Import Agribalyse LCI database from SimaPro
agribalyse_db_simapro: bw2io.importers.base_lci.LCIImporter = import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths = [LCI_agribalyse_simapro_folderpath / "AGB.CSV"],
                                                                                             db_name = agribalyse_db_name_simapro,
                                                                                             encoding = "latin-1",
                                                                                             delimiter = "\t",
                                                                                             verbose = True)
agribalyse_db_simapro.apply_strategy(unregionalize_biosphere)

agribalyse_db_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                             biosphere_db_name = biosphere_db_name_simapro,
                                             biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                             other_biosphere_databases = None,
                                             linking_order = None,
                                             relink = False,
                                             strip = True,
                                             case_insensitive = True,
                                             remove_special_characters = False,
                                             verbose = True), verbose = True)

agribalyse_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                             excel_migration_filepath = LCI_agribalyse_simapro_folderpath / "custom_migration_AGB.xlsx",
                                             migrate_activities = False,
                                             migrate_exchanges = True),
                                    verbose = True)

agribalyse_db_simapro.apply_strategy(partial(link.link_activities_internally,
                                             production_exchanges = True,
                                             substitution_exchanges = True,
                                             technosphere_exchanges = True,
                                             relink = False,
                                             strip = True,
                                             case_insensitive = True,
                                             remove_special_characters = False,
                                             verbose = True), verbose = True)

print("\n------- Statistics")
agribalyse_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = agribalyse_db_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)
print("\n------- Statistics")
agribalyse_db_simapro.statistics()

# Delete agribalyse database if already existing
if agribalyse_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + agribalyse_db_name_simapro)
    del bw2data.databases[agribalyse_db_name_simapro]

# Write database
print("\n------- Write database: " + agribalyse_db_name_simapro)
agribalyse_db_simapro.write_database()

# # Create a database object that will be used afterwards to update the background
# agribalyse_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(agribalyse_db_name_updated_simapro)
# agribalyse_db_updated_simapro.data: list[dict] = copy.deepcopy(agribalyse_db_simapro.data)

# # Rename the database with the new name
# agribalyse_db_updated_simapro.apply_strategy(partial(change_database_name,
#                                                      new_db_name = agribalyse_db_name_updated_simapro,
#                                                      ))

# Free up memory
del agribalyse_db_simapro


#%% Import AgriFootprint LCI database from SimaPro
agrifootprint_db_simapro: bw2io.importers.base_lci.LCIImporter = import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths = [LCI_agrifootprint_simapro_folderpath / "AGF.CSV"],
                                                                                                db_name = agrifootprint_db_name_simapro,
                                                                                                encoding = "latin-1",
                                                                                                delimiter = "\t",
                                                                                                verbose = True)
agrifootprint_db_simapro.apply_strategy(unregionalize_biosphere)

agrifootprint_db_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                                biosphere_db_name = biosphere_db_name_simapro,
                                                biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                                other_biosphere_databases = None,
                                                linking_order = None,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

agrifootprint_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                                excel_migration_filepath = LCI_agrifootprint_simapro_folderpath / "custom_migration_AGF_technosphere.xlsx",
                                                migrate_activities = False,
                                                migrate_exchanges = True),
                                        verbose = True)

agrifootprint_db_simapro.apply_strategy(partial(migrate_from_excel_file,
                                                excel_migration_filepath = LCI_agrifootprint_simapro_folderpath / "custom_migration_AGF_substitution.xlsx",
                                                migrate_activities = False,
                                                migrate_exchanges = True),
                                        verbose = True)

agrifootprint_db_simapro.apply_strategy(partial(link.link_activities_internally,
                                                production_exchanges = True,
                                                substitution_exchanges = True,
                                                technosphere_exchanges = True,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

print("\n------- Statistics")
agrifootprint_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = agrifootprint_db_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)
print("\n------- Statistics")
agrifootprint_db_simapro.statistics()

# Delete agrifootprint database if already existing
if agrifootprint_db_name_simapro in bw2data.databases:
    print("\n------- Delete database: " + agrifootprint_db_name_simapro)
    del bw2data.databases[agrifootprint_db_name_simapro]

# Write database
print("\n------- Write database: " + agrifootprint_db_name_simapro)
agrifootprint_db_simapro.write_database()

# # Create a database object that will be used afterwards to update the background
# agrifootprint_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(agrifootprint_db_name_updated_simapro)
# agrifootprint_db_updated_simapro.data: list[dict] = copy.deepcopy(agrifootprint_db_simapro.data)

# # Rename the database with the new name
# agrifootprint_db_updated_simapro.apply_strategy(partial(change_database_name,
#                                                         new_db_name = agrifootprint_db_name_updated_simapro,
#                                                         ))

# Free up memory
del agrifootprint_db_simapro


#%% Import ecoinvent data from ecoinvent XML setup
ecoinvent_db_xml: bw2io.importers.ecospold2.SingleOutputEcospold2Importer = import_XML_LCI_inventories(XML_LCI_filepath = LCI_ecoinvent_xml_datasets_folderpath_temp,
                                                                                                       db_name = ecoinvent_db_name_xml,
                                                                                                       biosphere_db_name = biosphere_db_name_xml,
                                                                                                       db_model_type_name = "cutoff",
                                                                                                       db_process_type_name = "unit",
                                                                                                       verbose = True)

print("\n-----------Linking statistics of current database import")
ecoinvent_db_xml.statistics()
print()

# Create the biosphere from XML file containing all elementary exchanges
biosphere_flows_from_xml_elementary_exchanges: list[dict] = create_XML_biosphere_from_elmentary_exchanges_file(filepath_ElementaryExchanges = LCIA_XML_elementary_exchanges_filepath_temp,
                                                                                                               biosphere_db_name = biosphere_db_name_xml)

# Delete biosphere database from XML if already existing
if biosphere_db_name_xml in bw2data.databases:
    print("\n------- Delete database: " + biosphere_db_name_xml)
    del bw2data.databases[biosphere_db_name_xml]

# Register the XML biosphere database
print("\n-----------Write database: " + biosphere_db_name_xml)
bw2data.Database(biosphere_db_name_xml).write({(m["database"], m["code"]): m for m in biosphere_flows_from_xml_elementary_exchanges})

# Link biosphere flows to imported ecoinvent biosphere (from XML files)
ecoinvent_db_xml.apply_strategy(partial(link.link_biosphere_flows_externally,
                                        biosphere_db_name = biosphere_db_name_xml,
                                        biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                        other_biosphere_databases = None,
                                        linking_order = None,
                                        relink = False,
                                        strip = False,
                                        case_insensitive = False,
                                        remove_special_characters = False,
                                        verbose = True), verbose = True)

print("\n-----------Linking statistics of current database import")
ecoinvent_db_xml.statistics()
print()

# Delete database first, if existing
if ecoinvent_db_name_xml in bw2data.databases:
    print("\n-----------Delete database: " + ecoinvent_db_name_xml)
    del bw2data.databases[ecoinvent_db_name_xml]

print("\n-----------Write database: " + ecoinvent_db_name_xml)
ecoinvent_db_xml.write_database(overwrite = False)
print()

# Import ecoinvent LCIA methods from Excel file
xml_lcia_methods: list[dict] = import_XML_LCIA_methods(XML_LCIA_filepath = LCIA_XML_filepath_temp,
                                                       biosphere_db_name = biosphere_db_name_xml,
                                                       ecoinvent_version = None)

print("\n-----------Write methods from ecoinvent Excel")
register_XML_LCIA_methods(methods = xml_lcia_methods)

# Free up memory
del ecoinvent_db_xml, xml_lcia_methods, biosphere_flows_from_xml_elementary_exchanges



#%% Create JSON files containing biosphere flow data
ecoinvent_db_xml_migrated: bw2io.importers.ecospold2.SingleOutputEcospold2Importer = import_XML_LCI_inventories(XML_LCI_filepath = LCI_ecoinvent_xml_datasets_folderpath,
                                                                                                                db_name = ecoinvent_db_name_xml_migrated,
                                                                                                                biosphere_db_name = biosphere_db_name_simapro,
                                                                                                                db_model_type_name = "cutoff",
                                                                                                                db_process_type_name = "unit",
                                                                                                                verbose = True)

# Create biosphere from XML LCI data
biosphere_flows_from_XML_LCI_data: list[dict] = create_XML_biosphere_from_LCI(db = ecoinvent_db_xml_migrated,
                                                                              biosphere_db_name = biosphere_db_name_simapro)

# Read excel file containing the LCIA methods from ecoinvent
df_LCIA_methods_ecoinvent: pd.DataFrame = pd.read_excel(LCIA_XML_filepath, sheet_name = LCIA_XML_sheetname)

# Create a list with biosphere flows that are not used in any of the ecoinvent methods
not_used_flows: dict = elementary_flows_that_are_not_used_in_XML_methods(elementary_flows = biosphere_flows_from_XML_LCI_data, method_df = df_LCIA_methods_ecoinvent)

# Write dataframe of flows that are not used
pd.DataFrame(list(not_used_flows.values())).to_excel(output_path / filename_biosphere_flows_not_specified_in_XML_methods, index = None)

# Exclude the flows that are not used, those do not need to be migrated
biosphere_flows_from_XML_used: list[dict] = [m for m in biosphere_flows_from_XML_LCI_data if (m["database"], m["code"]) not in not_used_flows]

# Create the JSON object to be written
biosphere_flows_from_XML_used_json: dict = json.dumps({idx: m for idx, m in enumerate(biosphere_flows_from_XML_used)}, indent = 4)

# Write the unlinked biosphere data dictionary to a JSON file
with open(output_path / ("biosphere_flows_from_XML.json"), "w") as outfile:
    outfile.write(biosphere_flows_from_XML_used_json)

# Create the biosphere from registered biosphere database (here from SimaPro)
biosphere_flows_from_SimaPro: list[dict] = [dict(m) for m in bw2data.Database(biosphere_db_name_simapro)]

# Create the JSON object to be written
biosphere_flows_from_SimaPro_json: dict = json.dumps({idx: dict(m) for idx, m in enumerate(biosphere_flows_from_SimaPro)}, indent = 4)

# Write the unlinked biosphere data dictionary to a JSON file
with open(output_path / ("biosphere_flows_from_SimaPro.json"), "w") as outfile:
    outfile.write(biosphere_flows_from_SimaPro_json)
    
# Free up memory
del biosphere_flows_from_SimaPro_json, biosphere_flows_from_XML_used_json

#%% Harmonize biospheres and create migration JSON

# Load dataframe with manually checked biosphere flows
manually_checked_SBERT_biosphere_names: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_SBERT_biosphere_names_validated)

# Harmonize the two biospheres
biosphere_harmonization: dict = create_harmonized_biosphere_migration(biosphere_flows_1 = biosphere_flows_from_XML_used,
                                                                      biosphere_flows_2 = biosphere_flows_from_SimaPro,
                                                                      manually_checked_SBERTs = manually_checked_SBERT_biosphere_names)

# Write excels
pd.DataFrame([{**{"FROM_" + k: v for k, v in FROM.items()}, **{"TO_" + k: v for k, v in TO.items()}}for FROM, TO in biosphere_harmonization["successfully_migrated_biosphere_flows"]]).to_excel(output_path / "biosphere_flows_successfully_migrated.xlsx")
pd.DataFrame([{**{"FROM_" + k: v for k, v in FROM.items()}}for FROM, _ in biosphere_harmonization["unsuccessfully_migrated_biosphere_flows"]]).to_excel(output_path / "biosphere_flows_unuccessfully_migrated.xlsx")
pd.DataFrame(biosphere_harmonization["SBERT_to_map"]).to_excel(output_path / "biosphere_flows_SBERT_to_map.xlsx")

# Retrieve the biosphere harmonization dictionary
biosphere_migration_data: dict = biosphere_harmonization["biosphere_migration"]

# Create the JSON object to be written
biosphere_migration_data_in_json_format = json.dumps(biosphere_migration_data, indent = 3)

# Write the biosphere dictionary to a JSON file
with open(filepath_biosphere_migration_data, "w") as outfile:
   outfile.write(biosphere_migration_data_in_json_format)

# Free up memory
del biosphere_harmonization, biosphere_migration_data, biosphere_migration_data_in_json_format

aaa = [m for m in biosphere_flows_from_SimaPro if "Water" in m["name"] and m["top_category"] == "water" and m["location"] == "GLO" and "ground" in m["sub_category"]]

#%% Remove unused flows
def remove_unused_biosphere_flows(db):
    for ds in db:
        ds["exchanges"]: list = [m for m in ds["exchanges"] if not (m["type"] == "biosphere" and (biosphere_db_name_simapro, m["code"]) in not_used_flows)]
    return db

# Apply strategy and remove unused flows
ecoinvent_db_xml_migrated.apply_strategy(remove_unused_biosphere_flows)

# The amount of XML biosphere flows should be the same as in the statistics
ecoinvent_db_xml_migrated.statistics()

#%% Replace the XML code with the one from SimaPro
# def replace_XML_code_field_with_SimaPro_code(XML_db):
    
#     # Create a mapping file from activity and reference product codes that are found in the ecoinvent SimaPro database
#     mapping: dict = {m["activity_code"] + "_" + m["reference_product_code"]: m["code"] for m in ecoinvent_db_simapro if m["activity_code"] is not None and m["reference_product_code"] is not None}
    
#     # Initialize counter
#     counter: int = 0
    
#     # Loop through each inventory from the XML database
#     for ds in XML_db:
        
#         # Try to find the corresponding SimaPro code using the mapping created beforehand
#         new_code: (str | None) = mapping.get(ds["code"])
        
#         # Go to next if no new code was found
#         if new_code is None:
#             continue
        
#         # Update the code field
#         ds["code"]: str = new_code
        
#         # Increase counter
#         counter += 1
        
#         # Loop through the exchanges to update the production exchange as well
#         for exc in ds["exchanges"]:
            
#             # If the current exchange is not of type production, continue
#             if exc["type"] != "production":
#                 continue
            
#             # Update code and input fields
#             exc["code"]: str = new_code
#             exc["input"]: tuple = (ds["database"], new_code)
    
#     # Print how many codes were changed
#     print("{} from {} code(s) were updated with the respective SimaPro code".format(counter, len(XML_db)))
    
#     return XML_db

# # Apply strategy and update the code of XML inventories with the respecting code from SimaPro inventories
# ecoinvent_db_xml_migrated.apply_strategy(replace_XML_code_field_with_SimaPro_code)

#%% Migrate biosphere flows and register ecoinvent XML database

# Apply biosphere migration
ecoinvent_db_xml_migrated.apply_strategy(partial(migrate_from_json_file,
                                                 json_migration_filepath = filepath_biosphere_migration_data,
                                                 migrate_activities = False,
                                                 migrate_exchanges = True),
                                         verbose = True)

ecoinvent_db_xml_migrated.apply_strategy(partial(link.remove_linking,
                                                 production_exchanges = True,
                                                 substitution_exchanges = True,
                                                 technosphere_exchanges = True,
                                                 biosphere_exchanges = True), verbose = True)

ecoinvent_db_xml_migrated.apply_strategy(partial(link.link_activities_internally,
                                                 production_exchanges = True,
                                                 substitution_exchanges = True,
                                                 technosphere_exchanges = True,
                                                 relink = False,
                                                 strip = True,
                                                 case_insensitive = True,
                                                 remove_special_characters = False,
                                                 verbose = True), verbose = True)

# Apply external linking of biosphere flows
ecoinvent_db_xml_migrated.apply_strategy(partial(link.link_biosphere_flows_externally,
                                                 biosphere_db_name = biosphere_db_name_simapro,
                                                 biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                                 other_biosphere_databases = None,
                                                 linking_order = None,
                                                 relink = False,
                                                 strip = True,
                                                 case_insensitive = True,
                                                 remove_special_characters = False,
                                                 verbose = True), verbose = True)

# Write unlinked biosphere flows to XLSX
print("\n-----------Write unlinked flows to excel file")
ecoinvent_db_xml_migrated.write_excel(only_unlinked = True)
    
# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
ecoinvent_db_xml_migrated.statistics()
print()
 
# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = ecoinvent_db_xml_migrated,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)

# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
ecoinvent_db_xml_migrated.statistics()
print()

# Delete database first, if existing
if ecoinvent_db_name_xml_migrated in bw2data.databases:
    print("\n-----------Delete database: " + ecoinvent_db_name_xml_migrated)
    del bw2data.databases[ecoinvent_db_name_xml_migrated]

# Write database
print("\n-----------Write database: " + ecoinvent_db_name_xml_migrated)
ecoinvent_db_xml_migrated.write_database(overwrite = False)
print()

# Free up memory
del ecoinvent_db_xml_migrated


#%% Create correspondence mapping
correspondence_files_and_versions: list[tuple] = [("Correspondence-File-v3.1-v3.2.xlsx", (3, 1), (3, 2)),
                                                  ("Correspondence-File-v3.2-v3.3.xlsx", (3, 2), (3, 3)),
                                                  ("Correspondence-File-v3.3-v3.4.xlsx", (3, 3), (3, 4)),
                                                  ("Correspondence-File-v3.4-v3.5.xlsx", (3, 4), (3, 5)),
                                                  ("Correspondence-File-v3.5-v3.6.xlsx", (3, 5), (3, 6)),
                                                  ("Correspondence-File-v3.6-v3.7.1.xlsx", (3, 6), (3, 7, 1)),
                                                  ("Correspondence-File-v3.7.1-v3.8.xlsx", (3, 7, 1), (3, 8)),
                                                  ("Correspondence-File-v3.8-v3.9.1.xlsx", (3, 8), (3, 9, 1)),
                                                  ("Correspondence-File-v3.8-v3.9.xlsx", (3, 8), (3, 9)),
                                                  ("Correspondence-File-v3.9.1-v3.10.xlsx", (3, 9, 1), (3, 10)),
                                                  ("Correspondence-File-v3.10.1-v3.11.xlsx", (3, 10, 1), (3, 11)),
                                                  ("Correspondence-File-v3.10-v3.10.1.xlsx", (3, 10), (3, 10, 1)),
                                                  ("Correspondence-File-v3.11-v3.12.xlsx", (3, 11), (3, 12)),
                                                  ]

# Create correspondence object
correspondence_obj: Correspondence = Correspondence(ecoinvent_model_type = "cutoff")

# Add the correspondence data to the correspondence object
for filename, FROM_version, TO_version in correspondence_files_and_versions:
    correspondence_obj.read_correspondence_dataframe(filepath_correspondence_excel = here.parent / "data" / "correspondence" / filename,
                                                     FROM_version = FROM_version,
                                                     TO_version = TO_version
                                                     )
    
# Get the standardized correspondence data and write to xlsx
correspondence_standardized_df: pd.DataFrame = correspondence_obj.standardized_df
correspondence_standardized_df.to_excel(output_path / "correspondence_files_standardized.xlsx", index = False)

#%% Specify the activities that can be mapped to
activities_to_migrate_to: list[dict] = [m.as_dict() for m in bw2data.Database(ecoinvent_db_name_xml_migrated)]

# Initialize the activity harmonization class
ah: ActivityHarmonization = ActivityHarmonization()

# Add the items to which should be migrated to
for ds in activities_to_migrate_to:
    source: ActivityDefinition = ActivityDefinition(activity_code = ds.get("activity_code"), 
                                                    reference_product_code = ds.get("reference_product_code"),
                                                    activity_name = ds.get("activity_name"),
                                                    reference_product_name = ds.get("reference_product_name"),
                                                    name = ds.get("name"),
                                                    simapro_name = ds.get("SimaPro_name"),
                                                    location = ds.get("location"),
                                                    unit = ds.get("unit")
                                                    )
 
    # ah.add_TO(source = copy.deepcopy(source), target = copy.deepcopy(ds), multiplier = 1)
    ah.add_TO(source = source, target = copy.deepcopy(ds), multiplier = 1)

# Specify the fields to which should be mapped to
TO_fields = ("code",
             "name",
             "SimaPro_name",
             "categories",
             "top_category",
             "sub_category",
             "SimaPro_categories",
             "unit",
             "SimaPro_unit",
             "location")

#%% Trigger the encoding of the SBERT model from the TO's by calling the '.SBERT_mapping'
# This is a heavy calculation and will be done here once so that it can be reused
ah.SBERT_mapping

#%% Create default variables to log data
unsuccessfully_migrated: list[dict] = []
successfully_migrated: list[dict] = []

#%% Custom functions to facilitate repetitive tasks
def add_correspondence_mappings(activity_harmonization_obj: ActivityHarmonization,
                                correspondence_obj: Correspondence,
                                FROM_version: tuple[int, int],
                                TO_version: tuple[int, int]) -> None:
    
    # Create tuple of from and to version
    correspondence_from_to_version: tuple[tuple[int, int], tuple[int, int]] = (FROM_version, TO_version)

    # Interlink correspondence files
    correspondence_obj.interlink_correspondence_files(FROM_version, TO_version)
    interlinked_df: pd.DataFrame = correspondence_obj.df_interlinked_data[correspondence_from_to_version]
    
    # Add correspondence mappings to activity harmonization class
    for idx, row in interlinked_df.iterrows():
        
        # Create source activity definition
        source: ActivityDefinition = ActivityDefinition(activity_code = row["FROM_activity_uuid"],
                                                        reference_product_code = row["FROM_reference_product_uuid"],
                                                        activity_name = row["FROM_activity_name"],
                                                        reference_product_name = row["FROM_reference_product_name"],
                                                        name = None,
                                                        simapro_name = None,
                                                        location = row["FROM_location"],
                                                        unit = row["FROM_unit"]
                                                        )
        # Create target activity definition
        target: ActivityDefinition = ActivityDefinition(activity_code = row["TO_activity_uuid"],
                                                        reference_product_code = row["TO_reference_product_uuid"],
                                                        activity_name = row["TO_activity_name"],
                                                        reference_product_name = row["TO_reference_product_name"],
                                                        name = None,
                                                        simapro_name = None,
                                                        location = row["TO_location"],
                                                        unit = row["TO_unit"]
                                                        )
        # Add to harmonization object
        activity_harmonization_obj.add_to_correspondence_mapping(source = source,
                                                                 target = target,
                                                                 multiplier = row.get("Multiplier")
                                                                 )


def add_custom_mappings(activity_harmonization_obj: ActivityHarmonization,
                        custom_mapping_df: pd.DataFrame) -> None:
    
    # Add custom mappings to activity harmonization class
    for idx, row in custom_mapping_df.replace({float("NaN"): None}).iterrows():
        
        # Create source activity definition
        source: ActivityDefinition = ActivityDefinition(activity_code = None,
                                                        reference_product_code = None,
                                                        activity_name = None,
                                                        reference_product_name = None,
                                                        name = row["FROM_name"],
                                                        simapro_name = None,
                                                        location = row["FROM_location"],
                                                        unit = row["FROM_unit"]
                                                        )
        
        # Create target activity definition
        target: ActivityDefinition = ActivityDefinition(activity_code = None,
                                                        reference_product_code = None,
                                                        activity_name = row.get("TO_activity_name"),
                                                        reference_product_name = row.get("TO_reference_product_name"),
                                                        name = row["TO_name"],
                                                        simapro_name = None,
                                                        location = row.get("TO_location"),
                                                        unit = row.get("TO_unit")
                                                        )
        # Add to harmonization object
        activity_harmonization_obj.add_to_custom_mapping(source = source,
                                                         target = target,
                                                         multiplier = row["multiplier"]
                                                         )


def map_activities(db_name: str,
                   exchanges_to_migrate: list[dict],
                   activity_harmonization_obj: ActivityHarmonization) -> (tuple, pd.DataFrame, pd.DataFrame):
    
    # Initialize tuples
    successful: tuple = ()
    unsuccessful: tuple = ()
    
    # Loop through each exchange that should be migrated
    for _, exc in exchanges_to_migrate.items():
        
        # Create a query as activity definition object
        query: ActivityDefinition = ActivityDefinition(activity_code = exc.get("activity_code"), 
                                                       reference_product_code = exc.get("reference_product_code"), 
                                                       activity_name = exc["activity_name"],
                                                       reference_product_name = exc["reference_product_name"],
                                                       name = exc["name"],
                                                       simapro_name = exc["SimaPro_name"],
                                                       location = exc["location"],
                                                       unit = exc["unit"]
                                                       )
        # Map directly
        direct: tuple = activity_harmonization_obj.map_directly(query = query)
        if direct != ():
            successful += ((direct[0][0], direct[0][1], "Direct mapping"),)
            continue
        
        # Map using custom mapping
        custom: tuple = activity_harmonization_obj.map_using_custom_mapping(query = query)
        if custom != ():
            successful += ((custom[0][0], custom[0][1], "Custom mapping"),)
            continue
        
        # Map using correspondence files
        correspondence: tuple = activity_harmonization_obj.map_using_correspondence_mapping(query = query)
        if correspondence != ():
            successful += ((correspondence[0][0], correspondence[0][1], "Correspondence mapping"),)
            continue
        
        # If we end here, we were unsuccessful. We add the query
        unsuccessful += (query,)
            
    # If there are unsuccessful queries, try using the SBERT model to find an equivalent
    if len(unsuccessful) > 0:
        sbert: tuple = activity_harmonization_obj.map_using_SBERT_mapping(queries = unsuccessful,
                                                                          n = 3,
                                                                          cutoff = 0.90)
        successful += tuple([m + ("SBERT mapping",) for m in sbert])
    
    # Print the amount of exchanges that were successfully migrated
    print("{} exchanges migrated".format(len(successful)))
    
    # Check if the FROM location matches with any of the TO locations
    # If that is the case, we remove all TOs but the one with the matching location and set multiplier to 1
    counter: int = 0
    for FROM, TOs, linking_method in successful:
        FROM_location: (str | None) = FROM.get("location")
        TOs_updated: list[tuple[dict, float]] = [(TO, float(1)) for TO, multiplier in TOs if TO.get("location") is not None and TO.get("location") == FROM_location]
        
        if len(TOs_updated) > 0 and len(TOs) > 1:
            TOs: list[tuple[dict, float]] = TOs_updated
            counter += 1
    
    # Print the amount of exchanges where the TOs were adapted since they matched with the FROM location
    print("{} exchanges were replaced with the same location".format(counter))
    
    # Initialize variables
    _successful: list = []
    successfully_migrated: list = []
    unsuccessfully_migrated: list = []
    
    # Loop through each successfully linked activity and bring to a format to write a dataframe
    for FROM, TOs, linking_method in successful:
        _successful += [FROM]
        FROM_dict: dict = {"FROM_" + k: v for k, v in FROM.items()}
        
        for TO, multiplier in TOs:
            TO_dict: dict = {"TO_" + m: TO[m] for m in TO_fields if m in TO}            
            successfully_migrated += [{"database": db_name, **FROM_dict, "multiplier": multiplier, **TO_dict, "linking_method": linking_method}]    
    
    # Loop through each unsuccessfully linked activity and bring to a format to write a dataframe
    for unsuccessful_query in unsuccessful:
        unsuccessful_data: dict = unsuccessful_query.data
        
        if unsuccessful_data not in _successful:
            unsuccessfully_migrated += [{"database": db_name, **{"FROM_" + k: v for k, v in unsuccessful_data.items()}}]

    return successful, successfully_migrated, unsuccessfully_migrated


def convert_to_JSON_migration_format(successful: tuple[dict, list, str]) -> dict:
    
    # Initialize variables
    fields: tuple[str] = ("name", "unit", "location")
    data: list = []
    
    # Loop through each successfully linked activity and bring to the valid migration format
    for FROM, TOs, linking_method in successful:
        FROM_tuple: tuple = tuple([FROM[m] for m in fields])
        
        TOs_prepared: list = []
        for TO, multiplier in TOs:
            TO_filtered: dict = {m: TO[m] for m in TO_fields if m in TO}            
            TOs_prepared += [(TO_filtered, multiplier)]
        
        for exc_type in ("technosphere", "substitution"):
            data += [((exc_type,) + FROM_tuple, TOs_prepared)]
        
    # Merge to a valid migration dictionary
    return {"fields": ("type",) + fields, "data": data}


#%% Create the Agribalyse background activity migration --> all ecoinvent v3.9.1 found in the background from Agribalyse should be updated to ecoinvent v3.12, if possible
agribalyse_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = import_SimaPro_LCI_inventories(SimaPro_CSV_LCI_filepaths = [LCI_agribalyse_simapro_folderpath / "AGB.CSV"],
                                                                                                     db_name = agribalyse_db_name_updated_simapro,
                                                                                                     encoding = "latin-1",
                                                                                                     delimiter = "\t",
                                                                                                     verbose = True)
agribalyse_db_updated_simapro.apply_strategy(unregionalize_biosphere)

agribalyse_db_updated_simapro.apply_strategy(partial(link.link_biosphere_flows_externally,
                                                     biosphere_db_name = biosphere_db_name_simapro,
                                                     biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                                     other_biosphere_databases = None,
                                                     linking_order = None,
                                                     relink = False,
                                                     strip = True,
                                                     case_insensitive = True,
                                                     remove_special_characters = False,
                                                     verbose = True), verbose = True)

agribalyse_db_updated_simapro.apply_strategy(partial(migrate_from_excel_file,
                                                     excel_migration_filepath = LCI_agribalyse_simapro_folderpath / "custom_migration_AGB.xlsx",
                                                     migrate_activities = False,
                                                     migrate_exchanges = True),
                                             verbose = True)

agribalyse_db_updated_simapro.apply_strategy(partial(link.link_activities_internally,
                                                     production_exchanges = True,
                                                     substitution_exchanges = True,
                                                     technosphere_exchanges = True,
                                                     relink = False,
                                                     strip = True,
                                                     case_insensitive = True,
                                                     remove_special_characters = False,
                                                     verbose = True), verbose = True)

print("\n------- Statistics")
agribalyse_db_updated_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
utils.add_unlinked_flows_to_biosphere_database(db = agribalyse_db_updated_simapro,
                                               biosphere_db_name_unlinked = unlinked_biosphere_db_name,
                                               biosphere_db_name = biosphere_db_name_simapro,
                                               verbose = True)
print("\n------- Statistics")
agribalyse_db_updated_simapro.statistics()

#####################################################
# COPYING FROM BACKGROUND IS TOO RESOURCE-INTENSIVE #
#####################################################
# Make a copy of the Agribalyse database as database object
# agribalyse_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(agribalyse_db_name_updated_simapro)
# agribalyse_db_updated_simapro_data: list[dict] = copy.deepcopy([{**ds.as_dict(), **{"exchanges": [exc.as_dict() for exc in ds.exchanges()]}} for ds in bw2data.Database(agribalyse_db_name_simapro)])
# agribalyse_db_updated_simapro.data: list[dict] = copy.deepcopy(agribalyse_db_updated_simapro_data)

# Rename the database with the new name
# agribalyse_db_updated_simapro.apply_strategy(partial(change_database_name,
#                                                      new_db_name = agribalyse_db_name_updated_simapro,
#                                                      ))
#####################################################
# COPYING FROM BACKGROUND IS TOO RESOURCE-INTENSIVE #
#####################################################

# We first extract all the IDs of the exchanges
agribalyse_exchanges_to_migrate_to_ecoinvent_IDs: set[tuple] = {exc["input"] for ds in copy.deepcopy(list(agribalyse_db_updated_simapro)) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# If the inventory is actually one of the exchange that should be mapped, we can exclude the exchanges within that inventory
agribalyse_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(agribalyse_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False) and (ds["database"], ds["code"]) not in agribalyse_exchanges_to_migrate_to_ecoinvent_IDs}
# agribalyse_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(agribalyse_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# Load dataframe with custom migration
agribalyse_delete_ref_prod_uuids_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_agribalyse_custom_mapping_harmonization, sheet_name = "delete_reference_product_uuids")
agribalyse_delete_ref_prod_uuids: list[tuple[str, str, str]] = [(m["name"], m["location"], m["unit"]) for idx, m in agribalyse_delete_ref_prod_uuids_df.iterrows()]

# Some reference product uuids are incorrect. We remove them manually.
for _, exc in agribalyse_exchanges_to_migrate_to_ecoinvent.items():
    
    # Set the reference product uuid to None if it is found in the df
    if (exc["name"], exc["location"], exc["unit"]) in agribalyse_delete_ref_prod_uuids:
        exc["reference_product_code"] = None

# Initialize the activity harmonization class
agribalyse_ah: ActivityHarmonization = copy.deepcopy(ah)

# Specify the from and to version for the correspondence mapping to be applied to the agribalyse database
agribalyse_correspondence_from_versions: list[tuple[int, int]] = [(3, 9, 1), (3, 8), (3, 6), (3, 3)]
agribalyse_correspondence_to_version: tuple[int, int] = (3, 11)

# Loop through each correspondence version that should be used for mapping
for agribalyse_correspondence_from_version in agribalyse_correspondence_from_versions:
    
    # Add the correspondence mappings to the harmonization object
    add_correspondence_mappings(activity_harmonization_obj = agribalyse_ah,
                                correspondence_obj = correspondence_obj,
                                FROM_version = agribalyse_correspondence_from_version,
                                TO_version = agribalyse_correspondence_to_version)


# Load dataframe with custom migration
agribalyse_custom_migration_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_agribalyse_custom_mapping_harmonization)

# Add the custom mappings to the harmonization object
add_custom_mappings(activity_harmonization_obj = agribalyse_ah,
                    custom_mapping_df = agribalyse_custom_migration_df)

# Find updates
agribalyse_successful, agribalyse_successful_for_df, agribalyse_unsuccessful_for_df = map_activities(db_name = agribalyse_db_name_updated_simapro,
                                                                                                     exchanges_to_migrate = agribalyse_exchanges_to_migrate_to_ecoinvent,
                                                                                                     activity_harmonization_obj = agribalyse_ah)
successfully_migrated += agribalyse_successful_for_df
unsuccessfully_migrated += agribalyse_unsuccessful_for_df

# Bring to valid migration format
AGB_background_ei_migration: dict = convert_to_JSON_migration_format(successful = agribalyse_successful)

# Create the JSON object to be written
AGB_background_ei_migration_in_json_format = json.dumps(AGB_background_ei_migration, indent = 3)

# Write the activity dictionary to a JSON file
with open(filepath_AGB_background_ei_migration_data, "w") as outfile:
   outfile.write(AGB_background_ei_migration_in_json_format)

# Free up memory
del agribalyse_ah, agribalyse_exchanges_to_migrate_to_ecoinvent, AGB_background_ei_migration, AGB_background_ei_migration_in_json_format

#%% Update the ecoinvent background activities in the Agribalyse database from v3.9.1 to v3.12 and register database
agribalyse_db_updated_simapro.apply_strategy(partial(link.remove_linking,
                                                     production_exchanges = False,
                                                     substitution_exchanges = True,
                                                     technosphere_exchanges = True,
                                                     biosphere_exchanges = False), verbose = True)

# Apply activity migration
agribalyse_db_updated_simapro.apply_strategy(partial(migrate_from_json_file,
                                                     json_migration_filepath = filepath_AGB_background_ei_migration_data,
                                                     migrate_activities = False,
                                                     migrate_exchanges = True),
                                             verbose = True)

# Link to ecoinvent externally
agribalyse_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                     link_to_databases = (ecoinvent_db_name_xml_migrated,),
                                                     link_production_exchanges = False,
                                                     link_substitution_exchanges = True,
                                                     link_technosphere_exchanges = True,
                                                     relink = False,
                                                     case_insensitive = True,
                                                     strip = True,
                                                     remove_special_characters = False,
                                                     verbose = True), verbose = True)

# Link remaining ones that were not updated
agribalyse_db_updated_simapro.apply_strategy(partial(link.link_activities_internally,
                                                     production_exchanges = False,
                                                     substitution_exchanges = True,
                                                     technosphere_exchanges = True,
                                                     relink = False,
                                                     strip = True,
                                                     case_insensitive = True,
                                                     remove_special_characters = False,
                                                     verbose = True), verbose = True)


# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
agribalyse_n_datasets, agribalyse_n_exchanges, agribalyse_n_unlinked = agribalyse_db_updated_simapro.statistics()
print()

# Write unlinked biosphere flows to XLSX, if existing
if agribalyse_n_unlinked > 0:
    print("\n-----------Write unlinked flows to excel file")
    agribalyse_db_updated_simapro.write_excel(only_unlinked = True)

# Delete database first, if existing
if agribalyse_db_name_updated_simapro in bw2data.databases:
    print("\n-----------Delete database: " + agribalyse_db_name_updated_simapro)
    del bw2data.databases[agribalyse_db_name_updated_simapro]

# Write database, but only if there are no unlinked flows
if agribalyse_n_unlinked == 0:
    print("\n-----------Write database: " + agribalyse_db_name_updated_simapro)
    agribalyse_db_updated_simapro.write_database(overwrite = False)
    print()

# Free up memory
del agribalyse_db_updated_simapro


#%% Create the WFDLB background activity migration --> all ecoinvent v3.5 found in the background from WFLDB should be updated to ecoinvent v3.12, if possible

# Make a copy of the WFLDB database as database object
wfldb_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(wfldb_db_name_updated_simapro)
wfldb_db_updated_simapro_data: list[dict] = [{**ds.as_dict(), **{"exchanges": [exc.as_dict() for exc in ds.exchanges()]}} for ds in bw2data.Database(wfldb_db_name_simapro)]
wfldb_db_updated_simapro.data: list[dict] = copy.deepcopy(wfldb_db_updated_simapro_data)
# wfldb_db_updated_simapro.data: list[dict] = copy.deepcopy(list(bw2data.Database(wfldb_db_name_simapro).load().values()))

# Rename the database with the new name
wfldb_db_updated_simapro.apply_strategy(partial(change_database_name,
                                                new_db_name = wfldb_db_name_updated_simapro,
                                                ))

# We first extract all the IDs of the exchanges
wfldb_exchanges_to_migrate_to_ecoinvent_IDs: set[tuple] = {exc["input"] for ds in copy.deepcopy(list(wfldb_db_updated_simapro)) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# If the inventory is actually one of the exchange that should be mapped, we can exclude the exchanges within that inventory
wfldb_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(wfldb_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False) and (ds["database"], ds["code"]) not in wfldb_exchanges_to_migrate_to_ecoinvent_IDs}
# wfldb_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(wfldb_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# Load dataframe with custom migration
wfldb_delete_ref_prod_uuids_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_wfldb_custom_mapping_harmonization, sheet_name = "delete_reference_product_uuids")
wfldb_delete_ref_prod_uuids: list[tuple[str, str, str]] = [(m["name"], m["location"], m["unit"]) for idx, m in wfldb_delete_ref_prod_uuids_df.iterrows()]

# Some reference product uuids are incorrect. We remove them manually.
for _, exc in wfldb_exchanges_to_migrate_to_ecoinvent.items():
    
    # Set the reference product uuid to None if it is found in the df
    if (exc["name"], exc["location"], exc["unit"]) in wfldb_delete_ref_prod_uuids:
        exc["reference_product_code"] = None

# Initialize the activity harmonization class
wfldb_ah: ActivityHarmonization = copy.deepcopy(ah)

# Specify the from and to version for the correspondence mapping to be applied to the wfldb database
wfldb_correspondence_from_versions: list[tuple[int, int]] = [(3, 5), (3, 10, 1), (3, 8), (3, 6), (3, 4)]
wfldb_correspondence_to_version: tuple[int, int] = (3, 11)

# Loop through each correspondence version that should be used for mapping
for wfldb_correspondence_from_version in wfldb_correspondence_from_versions:
    
    # Add the correspondence mappings to the harmonization object
    add_correspondence_mappings(activity_harmonization_obj = wfldb_ah,
                                correspondence_obj = correspondence_obj,
                                FROM_version = wfldb_correspondence_from_version,
                                TO_version = wfldb_correspondence_to_version)


# Load dataframe with custom migration
wfldb_custom_migration_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_wfldb_custom_mapping_harmonization, sheet_name = "custom_migration")

# Add the custom mappings to the harmonization object
add_custom_mappings(activity_harmonization_obj = wfldb_ah,
                    custom_mapping_df = wfldb_custom_migration_df)

# Find updates
wfldb_successful, wfldb_successful_for_df, wfldb_unsuccessful_for_df = map_activities(db_name = wfldb_db_name_updated_simapro,
                                                                                      exchanges_to_migrate = wfldb_exchanges_to_migrate_to_ecoinvent,
                                                                                      activity_harmonization_obj = wfldb_ah)
successfully_migrated += wfldb_successful_for_df
unsuccessfully_migrated += wfldb_unsuccessful_for_df

# Bring to valid migration format
WFLDB_background_ei_migration: dict = convert_to_JSON_migration_format(successful = wfldb_successful)

# Create the JSON object to be written
WFLDB_background_ei_migration_in_json_format = json.dumps(WFLDB_background_ei_migration, indent = 3)

# Write the activity dictionary to a JSON file
with open(filepath_WFLDB_background_ei_migration_data, "w") as outfile:
   outfile.write(WFLDB_background_ei_migration_in_json_format)

# Free up memory
del wfldb_ah, wfldb_db_updated_simapro_data, wfldb_exchanges_to_migrate_to_ecoinvent, WFLDB_background_ei_migration, WFLDB_background_ei_migration_in_json_format


#%% Update the ecoinvent background activities in the World Food LCA database from v3.5 to v3.12 and register database
wfldb_db_updated_simapro.apply_strategy(partial(link.remove_linking,
                                                production_exchanges = False,
                                                substitution_exchanges = True,
                                                technosphere_exchanges = True,
                                                biosphere_exchanges = False), verbose = True)

# Apply activity migration
wfldb_db_updated_simapro.apply_strategy(partial(migrate_from_json_file,
                                                json_migration_filepath = filepath_WFLDB_background_ei_migration_data,
                                                migrate_activities = False,
                                                migrate_exchanges = True),
                                        verbose = True)

# Link to ecoinvent externally
wfldb_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                link_to_databases = (ecoinvent_db_name_xml_migrated,),
                                                link_production_exchanges = False,
                                                link_substitution_exchanges = True,
                                                link_technosphere_exchanges = True,
                                                relink = False,
                                                case_insensitive = True,
                                                strip = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

# Link remaining ones that were not updated
wfldb_db_updated_simapro.apply_strategy(partial(link.link_activities_internally,
                                                production_exchanges = False,
                                                substitution_exchanges = True,
                                                technosphere_exchanges = True,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

wfldb_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                link_to_databases = (ecoinvent_db_name_simapro_unreg,),
                                                link_production_exchanges = False,
                                                link_substitution_exchanges = True,
                                                link_technosphere_exchanges = True,
                                                relink = False,
                                                case_insensitive = True,
                                                strip = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
wfldb_n_datasets, wfldb_n_exchanges, wfldb_n_unlinked = wfldb_db_updated_simapro.statistics()
print()

# Write unlinked biosphere flows to XLSX, if existing
if wfldb_n_unlinked > 0:
    print("\n-----------Write unlinked flows to excel file")
    wfldb_db_updated_simapro.write_excel(only_unlinked = True)

# Delete database first, if existing
if wfldb_db_name_updated_simapro in bw2data.databases:
    print("\n-----------Delete database: " + wfldb_db_name_updated_simapro)
    del bw2data.databases[wfldb_db_name_updated_simapro]

# Write database, but only if there are no unlinked flows
if wfldb_n_unlinked == 0:
    print("\n-----------Write database: " + wfldb_db_name_updated_simapro)
    wfldb_db_updated_simapro.write_database(overwrite = False)
    print()

# Free up memory
del wfldb_db_updated_simapro



#%% Create the SALCA background activity migration --> all ecoinvent v3.11 found in the background from SALCA should be updated to ecoinvent v3.12 from XML, if possible

# Make a copy of the SALCA database as database object
salca_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(salca_db_name_updated_simapro)
salca_db_updated_simapro_data: list[dict] = [{**ds.as_dict(), **{"exchanges": [exc.as_dict() for exc in ds.exchanges()]}} for ds in bw2data.Database(salca_db_name_simapro)]
salca_db_updated_simapro.data: list[dict] = copy.deepcopy(salca_db_updated_simapro_data)
# salca_db_updated_simapro.data: list[dict] = copy.deepcopy(list(bw2data.Database(salca_db_name_simapro).load().values()))

# Rename the database with the new name
salca_db_updated_simapro.apply_strategy(partial(change_database_name,
                                                new_db_name = salca_db_name_updated_simapro,
                                                ))

# We first extract all the IDs of the exchanges
salca_exchanges_to_migrate_to_ecoinvent_IDs: set[tuple] = {exc["input"] for ds in copy.deepcopy(list(salca_db_updated_simapro)) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# If the inventory is actually one of the exchange that should be mapped, we can exclude the exchanges within that inventory
salca_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(salca_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False) and (ds["database"], ds["code"]) not in salca_exchanges_to_migrate_to_ecoinvent_IDs}
# salca_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(salca_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# Load dataframe
salca_delete_ref_prod_uuids_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_salca_custom_mapping_harmonization, sheet_name = "delete_reference_product_uuids")
salca_delete_ref_prod_uuids: list[tuple[str, str, str]] = [(m["name"], m["location"], m["unit"]) for idx, m in salca_delete_ref_prod_uuids_df.iterrows()]

# Some reference product uuids are incorrect. We remove them manually.
for _, exc in salca_exchanges_to_migrate_to_ecoinvent.items():
    
    # Set the reference product uuid to None if it is found in the df
    if (exc["name"], exc["location"], exc["unit"]) in salca_delete_ref_prod_uuids:
        exc["reference_product_code"] = None

# Initialize the activity harmonization class
salca_ah: ActivityHarmonization = copy.deepcopy(ah)

# Specify the from and to version for the correspondence mapping to be applied to the salca database
salca_correspondence_from_versions: list[tuple[int, int]] = [(3, 10), (3, 9, 1), (3, 8), (3, 6), (3, 5)]
salca_correspondence_to_version: tuple[int, int] = (3, 11)

# Loop through each correspondence version that should be used for mapping
for salca_correspondence_from_version in salca_correspondence_from_versions:
    
    # Add the correspondence mappings to the harmonization object
    add_correspondence_mappings(activity_harmonization_obj = salca_ah,
                                correspondence_obj = correspondence_obj,
                                FROM_version = salca_correspondence_from_version,
                                TO_version = salca_correspondence_to_version)

# Load dataframe with custom migration
salca_custom_migration_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_salca_custom_mapping_harmonization)

# Add the custom mappings to the harmonization object
add_custom_mappings(activity_harmonization_obj = salca_ah,
                    custom_mapping_df = salca_custom_migration_df)

# Find updates
salca_successful, salca_successful_for_df, salca_unsuccessful_for_df = map_activities(db_name = salca_db_name_updated_simapro,
                                                                                      exchanges_to_migrate = salca_exchanges_to_migrate_to_ecoinvent,
                                                                                      activity_harmonization_obj = salca_ah)
successfully_migrated += salca_successful_for_df
unsuccessfully_migrated += salca_unsuccessful_for_df

# Bring to valid migration format
SALCA_background_ei_migration: dict = convert_to_JSON_migration_format(successful = salca_successful)

# Create the JSON object to be written
SALCA_background_ei_migration_in_json_format = json.dumps(SALCA_background_ei_migration, indent = 3)

# Write the activity dictionary to a JSON file
with open(filepath_SALCA_background_ei_migration_data, "w") as outfile:
   outfile.write(SALCA_background_ei_migration_in_json_format)

# Free up memory
del salca_ah, salca_db_updated_simapro_data, salca_exchanges_to_migrate_to_ecoinvent, SALCA_background_ei_migration, SALCA_background_ei_migration_in_json_format

#%% Update the ecoinvent background activities in the SALCA database from v3.11 to v3.12 (XML) and register database
salca_db_updated_simapro.apply_strategy(partial(link.remove_linking,
                                                production_exchanges = False,
                                                substitution_exchanges = True,
                                                technosphere_exchanges = True,
                                                biosphere_exchanges = False), verbose = True)

# Apply activity migration
salca_db_updated_simapro.apply_strategy(partial(migrate_from_json_file,
                                                json_migration_filepath = filepath_SALCA_background_ei_migration_data,
                                                migrate_activities = False,
                                                migrate_exchanges = True),
                                        verbose = True)

# Link to ecoinvent and wfldb externally
salca_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                link_to_databases = (ecoinvent_db_name_xml_migrated,),
                                                link_production_exchanges = False,
                                                link_substitution_exchanges = True,
                                                link_technosphere_exchanges = True,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

# Link remaining ones that were not updated
salca_db_updated_simapro.apply_strategy(partial(link.link_activities_internally,
                                                production_exchanges = False,
                                                substitution_exchanges = True,
                                                technosphere_exchanges = True,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

salca_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                link_to_databases = (ecoinvent_db_name_simapro_unreg,),
                                                link_production_exchanges = False,
                                                link_substitution_exchanges = True,
                                                link_technosphere_exchanges = True,
                                                relink = False,
                                                case_insensitive = True,
                                                strip = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

salca_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                link_to_databases = (wfldb_db_name_updated_simapro,),
                                                link_production_exchanges = False,
                                                link_substitution_exchanges = True,
                                                link_technosphere_exchanges = True,
                                                relink = False,
                                                strip = True,
                                                case_insensitive = True,
                                                remove_special_characters = False,
                                                verbose = True), verbose = True)

# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
salca_n_datasets, salca_n_exchanges, salca_n_unlinked = salca_db_updated_simapro.statistics()
print()

# Write unlinked biosphere flows to XLSX, if existing
if salca_n_unlinked > 0:
    print("\n-----------Write unlinked flows to excel file")
    salca_db_updated_simapro.write_excel(only_unlinked = True)

# Delete database first, if existing
if salca_db_name_updated_simapro in bw2data.databases:
    print("\n-----------Delete database: " + salca_db_name_updated_simapro)
    del bw2data.databases[salca_db_name_updated_simapro]
    
# Write database
print("\n-----------Write database: " + salca_db_name_updated_simapro)
salca_db_updated_simapro.write_database(overwrite = False)
print()

# Free up memory
del salca_db_updated_simapro


#%% Create the Agrifootprint activity migration --> all ecoinvent v3.10.1 found in the background from AgriFootprint should be updated to ecoinvent v3.12, if possible

# Make a copy of the Agrifootprint database as database object
agrifootprint_db_updated_simapro: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(agrifootprint_db_name_updated_simapro)
agrifootprint_db_updated_simapro_data: list[dict] = [{**ds.as_dict(), **{"exchanges": [exc.as_dict() for exc in ds.exchanges()]}} for ds in bw2data.Database(agrifootprint_db_name_simapro)]
agrifootprint_db_updated_simapro.data: list[dict] = copy.deepcopy(agrifootprint_db_updated_simapro_data)
# agrifootprint_db_updated_simapro.data: list[dict] = copy.deepcopy(list(bw2data.Database(agrifootprint_db_name_simapro).load().values()))

# Rename the database with the new name
agrifootprint_db_updated_simapro.apply_strategy(partial(change_database_name,
                                                        new_db_name = agrifootprint_db_name_updated_simapro,
                                                        ))

# We first extract all the IDs of the exchanges
agrifootprint_exchanges_to_migrate_to_ecoinvent_IDs: set[tuple] = {exc["input"] for ds in copy.deepcopy(list(agrifootprint_db_updated_simapro)) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# If the inventory is actually one of the exchange that should be mapped, we can exclude the exchanges within that inventory
agrifootprint_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(agrifootprint_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False) and (ds["database"], ds["code"]) not in agrifootprint_exchanges_to_migrate_to_ecoinvent_IDs}
# agrifootprint_exchanges_to_migrate_to_ecoinvent: dict = {(exc["name"], exc["unit"], exc["location"]): exc for ds in list(agrifootprint_db_updated_simapro) for exc in ds["exchanges"] if exc["type"] not in ["production", "biosphere"] and exc.get("is_ecoinvent", False)}

# Initialize the activity harmonization class
agrifootprint_ah: ActivityHarmonization = copy.deepcopy(ah)

# Specify the from and to version for the correspondence mapping to be applied to the agrifootprint database
agrifootprint_correspondence_from_versions: list[tuple[int, int]] = [(3, 10, 1)]
agrifootprint_correspondence_to_version: tuple[int, int] = (3, 11)

# Loop through each correspondence version that should be used for mapping
for agrifootprint_correspondence_from_version in agrifootprint_correspondence_from_versions:
    
    # Add the correspondence mappings to the harmonization object
    add_correspondence_mappings(activity_harmonization_obj = agrifootprint_ah,
                                correspondence_obj = correspondence_obj,
                                FROM_version = agrifootprint_correspondence_from_version,
                                TO_version = agrifootprint_correspondence_to_version)

# Load dataframe with custom migration
agrifootprint_custom_migration_df: pd.DataFrame = pd.read_excel(LCI_ecoinvent_xml_folderpath / filename_agrifootprint_custom_mapping_harmonization)

# Add the custom mappings to the harmonization object
add_custom_mappings(activity_harmonization_obj = agrifootprint_ah,
                    custom_mapping_df = agrifootprint_custom_migration_df)

# Find updates
agrifootprint_successful, agrifootprint_successful_for_df, agrifootprint_unsuccessful_for_df = map_activities(db_name = agrifootprint_db_name_updated_simapro,
                                                                                                              exchanges_to_migrate = agrifootprint_exchanges_to_migrate_to_ecoinvent,
                                                                                                              activity_harmonization_obj = agrifootprint_ah)
successfully_migrated += agrifootprint_successful_for_df
unsuccessfully_migrated += agrifootprint_unsuccessful_for_df

# Bring to valid migration format
AGF_background_ei_migration: dict = convert_to_JSON_migration_format(successful = agrifootprint_successful)

# Create the JSON object to be written
AGF_background_ei_migration_in_json_format = json.dumps(AGF_background_ei_migration, indent = 3)

# Write the activity dictionary to a JSON file
with open(filepath_AGF_background_ei_migration_data, "w") as outfile:
   outfile.write(AGF_background_ei_migration_in_json_format)

# Free up memory
del agrifootprint_ah, agrifootprint_db_updated_simapro_data, agrifootprint_exchanges_to_migrate_to_ecoinvent, AGF_background_ei_migration, AGF_background_ei_migration_in_json_format


#%% Update the ecoinvent background activities in the AgriFootprint database from v3.8 to v3.12 and register database
agrifootprint_db_updated_simapro.apply_strategy(partial(link.remove_linking,
                                                        production_exchanges = False,
                                                        substitution_exchanges = True,
                                                        technosphere_exchanges = True,
                                                        biosphere_exchanges = False), verbose = True)

# Apply activity migration
agrifootprint_db_updated_simapro.apply_strategy(partial(migrate_from_json_file,
                                                        json_migration_filepath = filepath_AGF_background_ei_migration_data,
                                                        migrate_activities = False,
                                                        migrate_exchanges = True),
                                        verbose = True)

# Link to ecoinvent externally
agrifootprint_db_updated_simapro.apply_strategy(partial(link.link_activities_externally,
                                                        link_to_databases = (ecoinvent_db_name_xml_migrated,),
                                                        link_production_exchanges = False,
                                                        link_substitution_exchanges = True,
                                                        link_technosphere_exchanges = True,
                                                        relink = False,
                                                        case_insensitive = True,
                                                        strip = True,
                                                        remove_special_characters = False,
                                                        verbose = True), verbose = True)

# Link remaining ones that were not updated
agrifootprint_db_updated_simapro.apply_strategy(partial(link.link_activities_internally,
                                                        production_exchanges = False,
                                                        substitution_exchanges = True,
                                                        technosphere_exchanges = True,
                                                        relink = False,
                                                        strip = True,
                                                        case_insensitive = True,
                                                        remove_special_characters = False,
                                                        verbose = True), verbose = True)


# Show statistic of current linking of database import
print("\n-----------Linking statistics of current database import")
agrifootprint_n_datasets, agrifootprint_n_exchanges, agrifootprint_n_unlinked = agrifootprint_db_updated_simapro.statistics()
print()

# Write unlinked biosphere flows to XLSX, if existing
if agrifootprint_n_unlinked > 0:
    print("\n-----------Write unlinked flows to excel file")
    agrifootprint_db_updated_simapro.write_excel(only_unlinked = True)

# Delete database first, if existing
if agrifootprint_db_name_updated_simapro in bw2data.databases:
    print("\n-----------Delete database: " + agrifootprint_db_name_updated_simapro)
    del bw2data.databases[agrifootprint_db_name_updated_simapro]

# Write database
print("\n-----------Write database: " + agrifootprint_db_name_updated_simapro)
agrifootprint_db_updated_simapro.write_database(overwrite = False)
print()

# Free up memory
del agrifootprint_db_updated_simapro


#%% Create migration tables
pd.DataFrame(successfully_migrated).to_excel(output_path / "background_ei_flows_successfully_migrated.xlsx")
pd.DataFrame(unsuccessfully_migrated).to_excel(output_path / "background_ei_flows_unsuccessfully_migrated.xlsx")

# see = [(m["name"], m["location"]) for m in bw2data.Database(ecoinvent_db_name_xml_migrated) if "Chemical, organic" in m["name"]]
# print(see)

#%% Run LCA calculation

# Methods to use for the LCA calculation
simapro_EF_LCIA_name: str = "Environmental Footprint v3.1"
ecoinvent_EF_LCIA_name: str = "EF v3.1"
simapro_methods: list[tuple[str]] = [m for m in bw2data.methods if m[0] == simapro_EF_LCIA_name]
ecoinvent_methods: list[tuple[str]] = [m for m in bw2data.methods if m[0] == ecoinvent_EF_LCIA_name]
methods_all: list[tuple] = list(bw2data.methods)

# Check if all specified methods are registered in the Brightway background
for method in simapro_methods + ecoinvent_methods:
    error: bool = False
    if method not in bw2data.methods:
        error: bool = True
        print("Method not registered: '{}'".format(method))

# If unregistered methods have been detected, raise error
if error:
    raise ValueError("Unregistered methods detected.")


#%% Comparison 1

# Extract all inventories
# ... from ecoinvent (SimaPro)
ecoinvent_simapro_inventories: list = [m for m in bw2data.Database(ecoinvent_db_name_simapro)]

# ... from ecoinvent (SimaPro), but unregionalized
ecoinvent_simapro_inventories_unreg: list = [m for m in bw2data.Database(ecoinvent_db_name_simapro_unreg)]

# ... from ecoinvent (XML)
ecoinvent_xml_inventories: list = [m for m in bw2data.Database(ecoinvent_db_name_xml)]

# Run LCA calculation
lca_ecoinvent_simapro: LCA_Calculation = LCA_Calculation(activities = ecoinvent_simapro_inventories,
                                                         methods = simapro_methods)
lca_ecoinvent_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_ecoinvent_simapro: dict[str, pd.DataFrame] = lca_ecoinvent_simapro.get_results(extended = True)
lca_ecoinvent_simapro.write_results(path = output_path,
                                    filename = "LCA_results_ecoinvent_simapro",
                                    use_timestamp_in_filename = True,
                                    extended = True)

# Run LCA calculation
lca_ecoinvent_simapro_unreg: LCA_Calculation = LCA_Calculation(activities = ecoinvent_simapro_inventories_unreg,
                                                               methods = simapro_methods)
lca_ecoinvent_simapro_unreg.calculate(calculate_LCIA_scores = True)
LCA_results_ecoinvent_simapro_unreg: dict[str, pd.DataFrame] = lca_ecoinvent_simapro_unreg.get_results(extended = True)
lca_ecoinvent_simapro_unreg.write_results(path = output_path,
                                          filename = "LCA_results_ecoinvent_simapro_unreg",
                                          use_timestamp_in_filename = True,
                                          extended = True)

# Run LCA calculation
lca_ecoinvent_xml: LCA_Calculation = LCA_Calculation(activities = ecoinvent_xml_inventories,
                                                     methods = ecoinvent_methods)
lca_ecoinvent_xml.calculate(calculate_LCIA_scores = True)
LCA_results_ecoinvent_xml: dict[str, pd.DataFrame] = lca_ecoinvent_xml.get_results(extended = True)
lca_ecoinvent_xml.write_results(path = output_path,
                                filename = "LCA_results_ecoinvent_xml",
                                use_timestamp_in_filename = True,
                                extended = True)

ecoinvent_xml_code_to_simapro_code_mapping: dict = {m["activity_code"] + "_" + m["reference_product_code"]: m["code"] for m in ecoinvent_simapro_inventories if m["activity_code"] is not None and m["reference_product_code"] is not None}

for m in LCA_results_ecoinvent_xml["LCIA_scores"]:
    m["Activity_code"]: str = ecoinvent_xml_code_to_simapro_code_mapping[m["Activity_code"]]

df_1: pd.DataFrame = pd.DataFrame(LCA_results_ecoinvent_simapro["LCIA_scores"] + LCA_results_ecoinvent_xml["LCIA_scores"])
df_1.to_csv(output_path / "comparison_ecoinvent_SimaPro_XML.csv")

df_LCIA_mapping: pd.DataFrame = pd.read_excel(here / "LCIA_method_mapping.xlsx")

LCIA_mapping: dict = {}

for idx, line in df_LCIA_mapping.iterrows():
    LCIA_mapping[literal_eval(line["SimaPro"])] = line["Standardized_name"]
    LCIA_mapping[literal_eval(line["XML"])] = line["Standardized_name"]

df_1["Method_standardized"] = [LCIA_mapping.get(m, "") for m in list(df_1["Method"])]
df_1.query("Method_standardized != ''").to_csv(output_path / "comparison_ecoinvent_SimaPro_XML_filtered.csv")

cfs_simapro: list[dict] = lca_ecoinvent_simapro.get_characterization_factors(extended = True)
cfs_xml: list[dict] = lca_ecoinvent_xml.get_characterization_factors(extended = True)

df_cfs_simapro: pd.DataFrame = pd.DataFrame(cfs_simapro)
df_cfs_xml: pd.DataFrame = pd.DataFrame(cfs_xml)

df_cfs_simapro.to_excel(output_path / "cfs_simapro.xlsx")
df_cfs_xml.to_excel(output_path / "cfs_xml.xlsx")


#%% Comparison 2

# Extract all inventories
# ... from Agribalyse (SimaPro) with ecoinvent v3.8 background
agribalyse_simapro_inventories: list = [m for m in bw2data.Database(agribalyse_db_name_simapro)]

# ... from Agribalyse (SimaPro) with ecoinvent v3.10 background
agribalyse_updated_simapro_inventories: list = [m for m in bw2data.Database(agribalyse_db_name_updated_simapro)]

# ... from WFLDB (SimaPro) with ecoinvent v3.5 background
wfldb_simapro_inventories: list = [m for m in bw2data.Database(wfldb_db_name_simapro)]

# ... from WFLDB (SimaPro) with ecoinvent v3.10 background
wfldb_updated_simapro_inventories: list = [m for m in bw2data.Database(wfldb_db_name_updated_simapro)]

# ... from SALCA (SimaPro) with ecoinvent v3.10 background
salca_simapro_inventories: list = [m for m in bw2data.Database(salca_db_name_simapro)]

# ... from SALCA (SimaPro) with ecoinvent v3.10 background
salca_updated_simapro_inventories: list = [m for m in bw2data.Database(salca_db_name_updated_simapro)]

# ... from AgriFootprint (SimaPro) with ecoinvent v3.8 background
agrifootprint_simapro_inventories: list = [m for m in bw2data.Database(agrifootprint_db_name_simapro)]

# ... from AgriFootprint (SimaPro) with ecoinvent v3.10 background
agrifootprint_updated_simapro_inventories: list = [m for m in bw2data.Database(agrifootprint_db_name_updated_simapro)]

# Run LCA calculation
lca_agribalyse_simapro: LCA_Calculation = LCA_Calculation(activities = agribalyse_simapro_inventories,
                                                          methods = simapro_methods)
lca_agribalyse_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_agribalyse_simapro: dict[str, pd.DataFrame] = lca_agribalyse_simapro.get_results(extended = True)


# Run LCA calculation
lca_agribalyse_updated_simapro: LCA_Calculation = LCA_Calculation(activities = agribalyse_updated_simapro_inventories,
                                                                  methods = simapro_methods)
lca_agribalyse_updated_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_agribalyse_updated_simapro: dict[str, pd.DataFrame] = lca_agribalyse_updated_simapro.get_results(extended = True)

# Run LCA calculation
lca_wfldb_simapro: LCA_Calculation = LCA_Calculation(activities = wfldb_simapro_inventories,
                                                     methods = simapro_methods)
lca_wfldb_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_wfldb_simapro: dict[str, pd.DataFrame] = lca_wfldb_simapro.get_results(extended = True)

# Run LCA calculation
lca_wfldb_updated_simapro: LCA_Calculation = LCA_Calculation(activities = wfldb_updated_simapro_inventories,
                                                             methods = simapro_methods)
lca_wfldb_updated_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_wfldb_updated_simapro: dict[str, pd.DataFrame] = lca_wfldb_updated_simapro.get_results(extended = True)

# Run LCA calculation
lca_salca_simapro: LCA_Calculation = LCA_Calculation(activities = salca_simapro_inventories,
                                                     methods = simapro_methods)
lca_salca_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_salca_simapro: dict[str, pd.DataFrame] = lca_salca_simapro.get_results(extended = True)

# Run LCA calculation
lca_salca_updated_simapro: LCA_Calculation = LCA_Calculation(activities = salca_updated_simapro_inventories,
                                                             methods = simapro_methods)
lca_salca_updated_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_salca_updated_simapro: dict[str, pd.DataFrame] = lca_salca_updated_simapro.get_results(extended = True)

# Run LCA calculation
lca_agrifootprint_simapro: LCA_Calculation = LCA_Calculation(activities = agrifootprint_simapro_inventories,
                                                     methods = simapro_methods)
lca_agrifootprint_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_agrifootprint_simapro: dict[str, pd.DataFrame] = lca_agrifootprint_simapro.get_results(extended = True)

# Run LCA calculation
lca_agrifootprint_updated_simapro: LCA_Calculation = LCA_Calculation(activities = agrifootprint_updated_simapro_inventories,
                                                                     methods = simapro_methods)
lca_agrifootprint_updated_simapro.calculate(calculate_LCIA_scores = True)
LCA_results_agrifootprint_updated_simapro: dict[str, pd.DataFrame] = lca_agrifootprint_updated_simapro.get_results(extended = True)

LCA_results_to_join: list[dict] = (LCA_results_agribalyse_simapro["LCIA_scores"] +
                                   LCA_results_agribalyse_updated_simapro["LCIA_scores"] +
                                   LCA_results_wfldb_simapro["LCIA_scores"] +
                                   LCA_results_wfldb_updated_simapro["LCIA_scores"] +
                                   LCA_results_salca_simapro["LCIA_scores"] +
                                   LCA_results_salca_updated_simapro["LCIA_scores"] +
                                   LCA_results_agrifootprint_simapro["LCIA_scores"] +
                                   LCA_results_agrifootprint_updated_simapro["LCIA_scores"]
                                   )

df_2: pd.DataFrame = pd.DataFrame(LCA_results_to_join)
df_2.to_csv(output_path / "comparison_updated_background.csv")

df_2["Method_standardized"] = [LCIA_mapping.get(m, "") for m in list(df_2["Method"])]
df_2.query("Method_standardized != ''").to_csv(output_path / "comparison_updated_background_filtered.xlsx")

#%% Get LCI emission contribution

used_codes_in_xml: dict = {m["Activity_code"]: True for m in LCA_results_ecoinvent_xml["LCIA_scores"]}
ecoinvent_simapro_inventories_equal_to_xml = [m for m in ecoinvent_simapro_inventories if used_codes_in_xml.get(m["code"], False)]

if len(ecoinvent_simapro_inventories_equal_to_xml) != len(ecoinvent_xml_inventories):
    raise ValueError("Length of simapro and xml ecoinvent databases are different: {} vs. {}".format(len(ecoinvent_simapro_inventories_equal_to_xml), len(ecoinvent_xml_inventories)))

# Run LCA calculation
bio_used_1: pd.DataFrame = extract_LCI_exchanges(acts = ecoinvent_simapro_inventories_equal_to_xml, db_name = "ecoinvent_SimaPro")
bio_used_2: pd.DataFrame = extract_LCI_exchanges(acts = ecoinvent_xml_inventories, db_name = "ecoinvent_XML")
bio_used_3: pd.DataFrame = extract_LCI_exchanges(acts = agribalyse_simapro_inventories, db_name = "agribalyse_SimaPro")
bio_used_4: pd.DataFrame = extract_LCI_exchanges(acts = agribalyse_updated_simapro_inventories, db_name = "agribalyse_SimaPro_updated")
bio_used_5: pd.DataFrame = extract_LCI_exchanges(acts = wfldb_simapro_inventories, db_name = "wfldb_SimaPro")
bio_used_6: pd.DataFrame = extract_LCI_exchanges(acts = wfldb_updated_simapro_inventories, db_name = "wfldb_SimaPro_updated")
bio_used_7: pd.DataFrame = extract_LCI_exchanges(acts = salca_simapro_inventories, db_name = "salca_SimaPro")
bio_used_8: pd.DataFrame = extract_LCI_exchanges(acts = salca_updated_simapro_inventories, db_name = "salca_SimaPro_updated")
bio_used_9: pd.DataFrame = extract_LCI_exchanges(acts = agrifootprint_simapro_inventories, db_name = "agrifootprint_SimaPro")
bio_used_10: pd.DataFrame = extract_LCI_exchanges(acts = agrifootprint_updated_simapro_inventories, db_name = "agrifootprint_SimaPro_updated")

bio_used: list[pd.DataFrame] = [bio_used_1,
                                bio_used_2,
                                bio_used_3,
                                bio_used_4,
                                bio_used_5,
                                bio_used_6,
                                bio_used_7,
                                bio_used_8,
                                bio_used_9,
                                bio_used_10
                                ]

df_bio_used: pd.DataFrame = pd.DataFrame(pd.concat(bio_used))
dcts: list[dict] = [bw2data.Database(m["Flow_database"]).get(m["Flow_code"]) for idx, m in df_bio_used.iterrows()]
df_bio_used["Flow_name"] = [m["name"] for m in dcts]
df_bio_used["Flow_categories"] = [m["categories"] for m in dcts]
df_bio_used["Flow_location"] = [m["location"] for m in dcts]
df_bio_used["Flow_unit"] = [m["unit"] for m in dcts]

df_bio_used.to_excel(output_path / "biosphere_flows_per_database.xlsx")


#%%
for method_name, _ in LCIA_mapping.items():
    method = bw2data.Method(method_name).load()
    print(str(len(method)) + " char. factors, " + str(method_name))
    print()

#%%
# import pandas as pd
water_use_method: tuple = ('Environmental Footprint v3.1', 'Water use')
lca_calculation: LCA_Calculation = LCA_Calculation(activities = [], methods = [water_use_method])
water_use_cfs: list[dict] = lca_calculation.get_characterization_factors([water_use_method])
water_use_cfs_df: pd.DataFrame = pd.DataFrame(water_use_cfs)
water_use_cfs_df.to_excel(output_path / "water_use_cfs.xlsx")


#%%
# Load JSON file
with open(output_path / ("biosphere_flows_from_XML.json"), "r") as f:
    bio_xml = json.load(f)
    
with open(output_path / ("biosphere_flows_from_SimaPro.json"), "r") as f:
    bio_simapro = json.load(f)

# Write to Excel
pd.DataFrame(list(bio_xml.values())).to_excel(output_path / "biosphere_flows_from_XML.xlsx", index = False)
pd.DataFrame(list(bio_simapro.values())).to_excel(output_path / "biosphere_flows_from_SimaPro.xlsx", index = False)

#%%
time_elapsed: datetime.timedelta = datetime.datetime.now() - start_time
pd.DataFrame([{"Log": "Creating the project took {} minutes".format(time_elapsed.total_seconds() / 60)}]).to_excel(output_path / "setting_project_time.xlsx")
