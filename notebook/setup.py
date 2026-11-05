import pathlib
here: pathlib.Path = pathlib.Path(__file__).parent

if __name__ == "__main__":
    import os
    os.chdir(here.parent)

import json
import bw2data
from  datetime import datetime
from rosetta import (BrightwayProject,
                     SimaProLCIImporter,
                     SimaProLCIAImporter,
                     LCIImporter)
from rosetta.methods import add_excluded_longterm_method


#%% File- and folderpaths, key variables
start_time = datetime.now()

# LCI and LCIA data
LCI_ecoinvent_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "ECO_fromSimaPro"
LCI_agribalyse_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "AGB_fromSimaPro"
LCI_agrifootprint_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "AGF_fromSimaPro"
LCI_wfldb_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "WFLDB_fromSimaPro"
LCI_salca_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "SALCA_fromSimaPro"
LCI_fooddk_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "FoodDK_fromSimaPro"
LCI_esu_simapro_folderpath: pathlib.Path = here.parent / "data" / "lci" / "ESU_fromSimaPro"
LCIA_SimaPro_CSV_folderpath: pathlib.Path = here.parent / "data" / "lcia" / "fromSimaPro"


# Generic and Brightway
if bw2data.__version__[0] >= 4:
    project_path: pathlib.Path = here.parent.parent  / "Brightway2.5_projects"
else:
    project_path: pathlib.Path = here.parent.parent / "Brightway2_projects"

project_path.mkdir(exist_ok = True)

print("\nWrite the name of your project here and press Enter:")
print("my project name = ")

# Command to type in your desired project name in the console
project_name: str = input() # "LCI and LCIA from SimaPro"
print("\n")

#%% Change brightway project directory and setup project
# Set project (if project already exists, raise error)
project: BrightwayProject = BrightwayProject(project_name, directory = project_path, new = True)
# bw2data.projects.delete_project(project_name)
# list(bw2data.projects)

#%% File- and folderpaths
# Setup output path
output_path: pathlib.Path = project.output_dir

#%% Defaults for key variables
biosphere_db_name_simapro: str = "biosphere3 - from SimaPro"
unlinked_biosphere_db_name: str = biosphere_db_name_simapro + " - unlinked"
ecoinvent_db_name_simapro: str = "ecoinvent v3.11 Cut-off - SimaPro - regionalized"
agribalyse_db_name_simapro: str = "Agribalyse v3.2 - SimaPro - regionalized (SimaPro background ecoinvent v3.9.1)"
agrifootprint_db_name_simapro: str = "AgriFootprint v7.0.1 - SimaPro - regionalized (SimaPro background ecoinvent v3.9.1)"
wfldb_db_name_simapro: str = "World Food LCA Database v3.5 - SimaPro - regionalized (SimaPro background ecoinvent v3.5)"
salca_db_name_simapro: str = "SALCA Database v3.11 - SimaPro - regionalized (SimaPro background ecoinvent v3.11)"
fooddk_db_name_simapro: str = "LCA Food DK - SimaPro"
esu_db_name_simapro: str = "ESU Services - SimaPro - regionalized (SimaPro background ecoinvent v3.11)"

#%% Import SimaPro LCIA methods and create SimaPro biosphere database
methods: SimaProLCIAImporter = SimaProLCIAImporter(LCIA_SimaPro_CSV_folderpath,
                                                   encoding = "latin-1",
                                                   delimiter = "\t")

methods.write_biosphere(biosphere_db_name_simapro)

methods.write_methods(biosphere_db_name_simapro, logs_dir = output_path)

SALCA_method_names: list[tuple] = [m for m in bw2data.methods if "SALCA" in m[0] and "no LT" not in m]
add_excluded_longterm_method(original_method = SALCA_method_names,
                             method_string_to_be_added = "no LT",
                             verbose = True)

project.export_overview(biosphere_db_name_simapro, output_path)

#%% Create JSON files containing biosphere flow data

# Create the biosphere from registered biosphere database (here from SimaPro)
biosphere_flows_from_SimaPro: list[dict] = [dict(m) for m in bw2data.Database(biosphere_db_name_simapro)]

# Create the JSON object to be written
biosphere_flows_from_SimaPro_json: dict = json.dumps({idx: dict(m) for idx, m in enumerate(biosphere_flows_from_SimaPro)}, indent = 4)

# Write the unlinked biosphere data dictionary to a JSON file
with open(output_path / ("biosphere_flows_from_SimaPro.json"), "w") as outfile:
    outfile.write(biosphere_flows_from_SimaPro_json)


#%% Import LCA Food DK database from SimaPro
fooddk_db_simapro: SimaProLCIImporter = SimaProLCIImporter(LCI_fooddk_simapro_folderpath / "FoodDK.CSV",
                                                           fooddk_db_name_simapro,
                                                           encoding = "latin-1",
                                                           delimiter = "\t")

fooddk_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

fooddk_db_simapro.migrate(LCI_fooddk_simapro_folderpath / "custom_migration_FoodDK.xlsx")

fooddk_db_simapro.link_internally()

print("\n------- Statistics")
fooddk_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
fooddk_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)
print("\n------- Statistics")
fooddk_db_simapro.statistics()

# Delete lca food dk database if already existing
# Write database
fooddk_db_simapro.write(overwrite = True)

# Free up memory
del fooddk_db_simapro


#%% Import ESU Services database from SimaPro
esu_db_simapro: SimaProLCIImporter = SimaProLCIImporter(LCI_esu_simapro_folderpath / "ESU.csv",
                                                        esu_db_name_simapro,
                                                        encoding = "latin-1",
                                                        delimiter = "\t")

esu_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

esu_db_simapro.migrate(LCI_esu_simapro_folderpath / "custom_migration_ESU.xlsx")

esu_db_simapro.link_internally()

print("\n------- Statistics")
esu_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
esu_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)
print("\n------- Statistics")
esu_db_simapro.statistics()

# Delete lca food dk database if already existing
# Write database
esu_db_simapro.write(overwrite = True)

# Free up memory
del esu_db_simapro


#%% Import the original ecoinvent database extract from SimaPro
original_ecoinvent_db_simapro: SimaProLCIImporter = SimaProLCIImporter(LCI_ecoinvent_simapro_folderpath / "ECO.CSV",
                                                                       ecoinvent_db_name_simapro,
                                                                       encoding = "latin-1",
                                                                       delimiter = "\t")

original_ecoinvent_db_simapro.migrate(LCI_ecoinvent_simapro_folderpath / "custom_migration_ECO.xlsx")

# Remove linking
original_ecoinvent_db_simapro.unlink(production = True,
                                     substitution = True,
                                     technosphere = True,
                                     biosphere = True)

# Link biosphere flows
original_ecoinvent_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
original_ecoinvent_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)

print("\n------- Statistics")
original_ecoinvent_db_simapro.statistics()


#%% Patterns to identify inventories from different databases

# # Specific patterns that are used to identify SALCA inventories
# SALCA_patterns: list[str] = ["SALCA", # abbreviation to identify SALCA inventories
#                             "SLACA", # WOW... I mean come on...
#                             "at plant/CH mix", # some CH mixes that were created without the SALCA abbreviation
#                             "maize silage, conservation, sect.", # This inventory does not contain the SALCA abbreviation in the SimaPro name but we still have to include it.
#                             "maize silage, horiz. silo, IP, conservation, sect", # This inventory does not contain the SALCA abbreviation in the SimaPro name but we still have to include it.
#                             "maize silage, tow. silo, IP, conservation, sect", # This inventory does not contain the SALCA abbreviation in the SimaPro name but we still have to include it.
#                             ]

# Specific patterns that are used to identify SALCA inventories
SALCA_patterns: list[str] = ["SALCA"]

# Specific patterns that are used to identify WFLDB inventories
WFLDB_patterns: list[str] = ["WFLDB", # because why not finding WFLDB inventories in SALCA/ecoinvent?
                             "Diesel combustion, in tractor/kg/", # Specific SALCA inventory that we need since it is internally referred to
                             "Shed, large, wood, non-insulated, fire-unprotected, at farm/m2/" # Specific SALCA inventory that we need since it is internally referred to
                             ]

#%% Import regionalized ecoinvent LCI database from SimaPro
ecoinvent_db_simapro: LCIImporter = original_ecoinvent_db_simapro.select(SALCA_patterns + WFLDB_patterns,
                                                                         exclude = True,
                                                                         db_name = ecoinvent_db_name_simapro)

ecoinvent_db_simapro.link_internally()

print("\n------- Statistics")
ecoinvent_db_simapro.statistics()

# Delete ecoinvent database if already existing
# Write database
ecoinvent_db_simapro.write(overwrite = True)



#%% Import WFLDB LCI database from SimaPro
wfldb_db_simapro: LCIImporter = original_ecoinvent_db_simapro.select(WFLDB_patterns,
                                                                     exclude = False,
                                                                     db_name = wfldb_db_name_simapro)

wfldb_db_simapro.extend(SimaProLCIImporter(LCI_wfldb_simapro_folderpath / "WFLDB.CSV",
                                           wfldb_db_name_simapro,
                                           encoding = "latin-1",
                                           delimiter = "\t"))

wfldb_db_simapro.rename(wfldb_db_name_simapro)

wfldb_db_simapro.migrate(LCI_wfldb_simapro_folderpath / "custom_migration_WFLDB.xlsx")

wfldb_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

wfldb_db_simapro.link_internally()

wfldb_db_simapro.link_to(ecoinvent_db_name_simapro,
                         production = False,
                         substitution = False,
                         technosphere = True,
                         relink = False)

print("\n------- Statistics")
wfldb_db_simapro.statistics()

# wfldb_db_simapro.write_excel(only_unlinked = True)
# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
wfldb_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)
print("\n------- Statistics")
wfldb_db_simapro.statistics()

# Delete wfldb database if already existing
# Write database
wfldb_db_simapro.write(overwrite = True)

# Free up memory
del wfldb_db_simapro

#%% Import SALCA LCI database from SimaPro
salca_db_simapro: LCIImporter = original_ecoinvent_db_simapro.select(SALCA_patterns,
                                                                     exclude = False,
                                                                     db_name = salca_db_name_simapro)

salca_db_simapro.migrate(LCI_salca_simapro_folderpath / "custom_migration_SALCA.xlsx")

salca_db_simapro.link_internally()

salca_db_simapro.link_to(ecoinvent_db_name_simapro, wfldb_db_name_simapro,
                         production = False,
                         substitution = False,
                         technosphere = True,
                         relink = False)

print("\n------- Statistics")
salca_db_simapro.statistics()
# salca_db_simapro.write_excel(only_unlinked = True)

# Delete ecoinvent database if already existing
# Write database
salca_db_simapro.write(overwrite = True)

# Free up memory
del salca_db_simapro


#%% Import Agribalyse LCI database from SimaPro
agribalyse_db_simapro: SimaProLCIImporter = SimaProLCIImporter(LCI_agribalyse_simapro_folderpath / "AGB.CSV",
                                                               agribalyse_db_name_simapro,
                                                               encoding = "latin-1",
                                                               delimiter = "\t")

agribalyse_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

agribalyse_db_simapro.migrate(LCI_agribalyse_simapro_folderpath / "custom_migration_AGB.xlsx")

agribalyse_db_simapro.link_internally()

print("\n------- Statistics")
agribalyse_db_simapro.statistics()

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
agribalyse_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)
print("\n------- Statistics")
agribalyse_db_simapro.statistics()

# Delete agribalyse database if already existing
# Write database
agribalyse_db_simapro.write(overwrite = True)

# Free up memory
del agribalyse_db_simapro

#%% Import AgriFootprint LCI database from SimaPro
agrifootprint_db_simapro: SimaProLCIImporter = SimaProLCIImporter(LCI_agrifootprint_simapro_folderpath / "AGF.CSV",
                                                                  agrifootprint_db_name_simapro,
                                                                  encoding = "latin-1",
                                                                  delimiter = "\t")

agrifootprint_db_simapro.link_biosphere(biosphere_db_name_simapro, unlinked_biosphere_db_name, relink = False)

agrifootprint_db_simapro.migrate(LCI_agrifootprint_simapro_folderpath / "custom_migration_AGF_technosphere.xlsx")

agrifootprint_db_simapro.migrate(LCI_agrifootprint_simapro_folderpath / "custom_migration_AGF_substitution.xlsx")

agrifootprint_db_simapro.link_internally()

print("\n------- Statistics")
agrifootprint_db_simapro.statistics()
# agrifootprint_db_simapro.write_excel(only_unlinked = True)

# Make a new biosphere database for the flows which are currently not linked
# Add unlinked biosphere flows with a custom function
agrifootprint_db_simapro.add_unlinked_to_biosphere(unlinked_biosphere_db_name, biosphere_db_name_simapro)
print("\n------- Statistics")
agrifootprint_db_simapro.statistics()

# Delete agrifootprint database if already existing
# Write database
agrifootprint_db_simapro.write(overwrite = True)

# Free up memory
del agrifootprint_db_simapro

#%%
print('Project created')
end_time = datetime.now()

print('Time elapsed' , str(round((end_time - start_time).seconds/60)), 'minutes')


#%% Extract metadata to excel
# import pandas as pd
# data: list[dict] = []

# # Loop through each database in the background
# for database_name in bw2data.databases:
#     print(database_name)
    
#     # Go on if it contains 'biosphere' in the name, since we are not interested in extracting biosphere flows
#     if "biosphere" in database_name:
#         continue
    
#     # Extract data and add to list
#     data += utils.extract_activity_list_with_metadata(database_name)
    
# # Convert to dataframe and write
# data_df: pd.DataFrame = pd.DataFrame(data)
# data_df.to_excel(output_path / "activity_metadata.xlsx", index = False)

# import pandas as pd
# from calculation import LCA_Calculation
# methods = [m for m in bw2data.methods if "SALCA" in m[0]]
# LCA_results: list[dict] = []

# for database_name in bw2data.databases:
#     print(database_name)
    
#     # Go on if it contains 'biosphere' in the name, since we will not calculate biosphere flows
#     if "biosphere" in database_name:
#         continue
    
#     activities: list = list(bw2data.Database(database_name))
#     lca_calculation: LCA_Calculation = LCA_Calculation(activities = activities, methods = methods)
#     lca_calculation.calculate(calculate_LCIA_scores = True)
#     LCIA_scores: list[dict] = lca_calculation.get_results(extended = True)["LCIA_scores"]
#     LCA_results += LCIA_scores
    
# LCA_results_df: pd.DataFrame = pd.DataFrame(LCA_results)
# LCA_results_df.to_excel(output_path / "activity_impacts.xlsx", index = False)

# #%% Example of how to run an LCA calculation

# # Methods to use for the LCA calculation
# simapro_EF_LCIA_name: str = "Environmental Footprint v3.1"
# simapro_methods: list[tuple[str]] = [m for m in bw2data.methods if m[0] == simapro_EF_LCIA_name]
# methods_all: list[tuple] = list(bw2data.methods)

# # Check if all specified methods are registered in the Brightway background
# for method in simapro_methods:
#     error: bool = False
#     if method not in bw2data.methods:
#         error: bool = True
#         print("Method not registered: '{}'".format(method))

# # If unregistered methods have been detected, raise error
# if error:
#     raise ValueError("Unregistered methods detected.")


# #%% LCA calculation

# # Extract all inventories
# # ... from ecoinvent v3.10 (SimaPro)
# ecoinvent_simapro_inventories: list = [m for m in bw2data.Database(ecoinvent_db_name_simapro)]

# # Run LCA calculation
# lca_calculation_ecoinvent: LCA_Calculation = LCA_Calculation(activities = ecoinvent_simapro_inventories,
#                                                              methods = simapro_methods,
#                                                              functional_amount = 1,
#                                                              cut_off_percentage = 0.001,
#                                                              exchange_level = 1,
#                                                              print_progress_bar = True)
# lca_calculation_ecoinvent.calculate_LCIA_scores()
# lca_calculation_ecoinvent.write_results(path = output_path,
#                                         filename = "ecoinvent_SimaPro",
#                                         use_timestamp_in_filename = False,
#                                         clean = True)

# # Extract all inventories
# # ... from Agribalyse v3.1 (SimaPro) with ecoinvent v3.8 background
# agribalyse_simapro_inventories: list = [m for m in bw2data.Database(agribalyse_db_name_simapro)]

# # Run LCA calculation
# lca_calculation_agribalyse: LCA_Calculation = LCA_Calculation(activities = agribalyse_simapro_inventories,
#                                                              methods = simapro_methods,
#                                                              functional_amount = 1,
#                                                              cut_off_percentage = 0.001,
#                                                              exchange_level = 1,
#                                                              print_progress_bar = True)
# lca_calculation_agribalyse.calculate_LCIA_scores()
# lca_calculation_agribalyse.write_results(path = output_path,
#                                          filename = "agribalyse_SimaPro",
#                                          use_timestamp_in_filename = False,
#                                          clean = True)

# # Extract all inventories
# # ... from SALCA v3.10 (SimaPro) with ecoinvent v3.10 background
# salca_simapro_inventories: list = [m for m in bw2data.Database(salca_db_name_simapro)]

# # Run LCA calculation
# lca_calculation_salca: LCA_Calculation = LCA_Calculation(activities = salca_simapro_inventories,
#                                                          methods = simapro_methods,
#                                                          functional_amount = 1,
#                                                          cut_off_percentage = 0.001,
#                                                          exchange_level = 1,
#                                                          print_progress_bar = True)
# lca_calculation_salca.calculate_LCIA_scores()
# lca_calculation_salca.write_results(path = output_path,
#                                     filename = "salca_SimaPro",
#                                     use_timestamp_in_filename = False,
#                                     clean = True)

# # Extract all inventories
# # ... from Agrifootprint v6.3 (SimaPro) with ecoinvent v3.8 background
# agrifootprint_simapro_inventories: list = [m for m in bw2data.Database(agrifootprint_db_name_simapro)]

# # Run LCA calculation
# lca_calculation_agrifootprint: LCA_Calculation = LCA_Calculation(activities = agrifootprint_simapro_inventories,
#                                                                  methods = simapro_methods,
#                                                                  functional_amount = 1,
#                                                                  cut_off_percentage = 0.001,
#                                                                  exchange_level = 1,
#                                                                  print_progress_bar = True)
# lca_calculation_agrifootprint.calculate_LCIA_scores()
# lca_calculation_agrifootprint.write_results(path = output_path,
#                                             filename = "agrifootprint_SimaPro",
#                                             use_timestamp_in_filename = False,
#                                             clean = True)

# # Extract all inventories
# # ... from WFLDB v3.5 (SimaPro) with ecoinvent v3.5 background
# wfldb_simapro_inventories: list = [m for m in bw2data.Database(wfldb_db_name_simapro)]

# # Run LCA calculation
# lca_calculation_wfldb: LCA_Calculation = LCA_Calculation(activities = wfldb_simapro_inventories,
#                                                          methods = simapro_methods,
#                                                          functional_amount = 1,
#                                                          cut_off_percentage = 0.001,
#                                                          exchange_level = 1,
#                                                          print_progress_bar = True)
# lca_calculation_wfldb.calculate_LCIA_scores()
# lca_calculation_wfldb.write_results(path = output_path,
#                                     filename = "wfldb_SimaPro",
#                                     use_timestamp_in_filename = False,
#                                     clean = True)


# #%% Export inventories to SimaPro CSV
# SimaPro_CSV_text_block: str = export_SimaPro_CSV(list_of_Brightway2_pewee_objects = ecoinvent_simapro_inventories[10:20],
#                                                  folder_path_SimaPro_CSV = output_path,
#                                                  file_name_SimaPro_CSV_without_ending = "10_exported_SimaPro_inventories",
#                                                  file_name_print_timestamp = True,
#                                                  separator = "\t",
#                                                  avoid_exporting_inventories_twice = True,
#                                                  csv_format_version = "7.0.0",
#                                                  decimal_separator = ".",
#                                                  date_separator = ".",
#                                                  short_date_format = "dd.MM.yyyy")

