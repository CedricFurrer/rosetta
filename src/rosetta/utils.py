import pathlib
import os

import uuid
import copy
import torch
import bw2io
import bw2data
import pathlib
import collections
import pandas as pd
from functools import partial
from sentence_transformers import SentenceTransformer, util
from . import helper as hp

starting: str = "------------"


#%% Change Brightway project directory path

def change_brightway_project_directory(BRIGHTWAY2_DIR: (pathlib.Path | str),
                                       verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(change_brightway_project_directory, locals())
    
    # Print statement
    if verbose:
        print(starting + "BRIGHTWAY2_DIR is set to the following path:\n" + str(BRIGHTWAY2_DIR) + "\n")
    
    # Those lines are directly taken from Brightway
    # It constructs some fields new and sets the path according to the one given by ourselves
    bw2data.projects._base_data_dir = str(BRIGHTWAY2_DIR)
    bw2data.projects._base_logs_dir = os.path.join(str(BRIGHTWAY2_DIR), "logs")
    bw2data.projects.db = bw2data.sqlite.SubstitutableDatabase(os.path.join(str(BRIGHTWAY2_DIR), "projects.db"), [bw2data.project.ProjectDataset])
    bw2data.projects.set_current("default", update = False)

#%% Return the amount of unlinked flows from a list of datasets by type

def linking_summary_dictionary(db_var):
    
    # Taken from 'db.statistics()' from Brightway
    # Make variable check
    hp.check_function_input_type(linking_summary_dictionary, locals())
    
    # Initialize empty dictionary
    unique_unlinked = collections.defaultdict(set)
    
    # Loop through the database
    for ds in db_var:
        
        # Loop through all unlinked exchanges
        for exc in (e for e in ds.get("exchanges", []) if not e.get("input")):
            
            # Add 
            if exc["type"] == "biosphere":
                unique_unlinked[exc.get("type")].add(hp.format_values(tuple([exc[m] for m in ("name", "top_category", "sub_category", "location", "unit")]),
                                                                      case_insensitive = True,
                                                                      strip = True,
                                                                      remove_special_characters = False))
                
            else:
                unique_unlinked[exc.get("type")].add(hp.format_values(tuple([exc[m] for m in ("name", "unit", "location")]),
                                                                      case_insensitive = True,
                                                                      strip = True,
                                                                      remove_special_characters = False))
    
    # For each exchange type, get the length of unlinked exchanges 
    unique_unlinked = {k: len(v) for k, v in unique_unlinked.items()}
    
    return unique_unlinked



#%% A function that uses the SBERT model to find the best match from a list

def map_using_SBERT(items_to_map: tuple, items_to_map_to: tuple, max_number: int = 1) -> pd.DataFrame:
    
    # Check function input type
    hp.check_function_input_type(map_using_SBERT, locals())
    
    # Raise error if max number is lower than 1
    if max_number < 1:
        raise ValueError("'max_number' argument needs to be greater or equal than 1 but currently is '{}'".format(max_number))
    
    # Path to where model might lay
    path: pathlib.Path = pathlib.Path(__file__).parent / "defaults" / "all-MiniLM-L6-v2"
    
    # Check if path exists
    if path.exists():
        model = SentenceTransformer(str(path))
    
    else:
        # model = SentenceTransformer("all-mpnet-base-v2")
        model = SentenceTransformer("all-MiniLM-L6-v2")

    # Compute embedding for both lists
    embeddings1 = model.encode(items_to_map, convert_to_tensor = True)
    embeddings2 = model.encode(items_to_map_to, convert_to_tensor = True)

    # Compute cosine-similarities
    cosine_scores = util.cos_sim(embeddings1, embeddings2)

    # Initialize variable
    data: list = []

    # Loop through each item from 'items_to_map' and extract the elements that were mapped to it with its respective cosine score
    for idx_I, scores_tensor in enumerate(cosine_scores):
        
        # Extract the scores (values) and its respective location (indice)
        values, indices = torch.sort(scores_tensor, descending = True)
        
        # Add the n (max_number) mapped items with the highest cosine score to the list
        data += [{"orig": items_to_map[idx_I],
                  "mapped": items_to_map_to[indice],
                  "score": float(value),
                  "ranking": idx} for idx, value, indice in zip(reversed(range(1, max_number + 1)), values[0:max_number], indices[0:max_number])]

    return pd.DataFrame(data)

#%% Functions to change database names and create copies of databases
def change_database_name(db_var,
                         new_db_name: str):
    
    # Make variable check
    hp.check_function_input_type(change_database_name, locals())
    
    # Loop through each inventory
    for ds in db_var:
        
        # Save old database name
        old_db_name: str = ds["database"]
        
        # Rename
        ds["database"]: str = new_db_name
        
        # Loop through each exchange of that inventory
        for exc in ds["exchanges"]:
            
            # Add database key to production exchange
            if exc["type"] == "production":
                exc["database"]: str = new_db_name
            
            # Update the input field with the new database name, if available
            if "input" in exc:
                if exc["input"][0] == old_db_name:
                    exc["input"]: tuple[str, str] = (new_db_name, exc["input"][1])
            
            # Delete the output field, if available
            try: del exc["output"]
            except: pass
                
    return db_var


def copy_brightway_database(db_name: str,
                            new_db_name: str) -> bw2io.importers.base_lci.LCIImporter:
    
    # Make variable check
    hp.check_function_input_type(copy_brightway_database, locals())
    
    # Check if the database that we want to copy is registered in Brightway. If not, raise error
    if db_name not in bw2data.databases:
        raise ValueError("Database '{}' is not registered in the Brightway background and can therefore not be copied. Available databases are:\n{}".format(db_name, bw2data.databases))
        
    # # Check if a database is already existing with the new name. If yes, we can not register a database with the new name and need to raise an error.
    # if new_db_name in bw2data.databases:
    #     raise ValueError("New database name '{}' can not be used because a database with this name already exists in Brightway. Use another name.".format(new_db_name))
    
    # Load data from the database and make a deepcopy
    db: list[dict] = [{**act.as_dict(), **{"exchanges": [exc.as_dict() for exc in act.exchanges()]}} for act in bw2data.Database(db_name)]
    copied: list[dict] = copy.deepcopy(db)
    
    # As brightway importer object
    db_as_obj: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(new_db_name)
    db_as_obj.data: list[dict] = copied
    
    # Change database name, only if the names are different
    if new_db_name != db_name:
        db_as_obj.apply_strategy(partial(change_database_name,
                                         new_db_name = new_db_name))
    
    return db_as_obj
    

# Extract metadata to excel
def extract_activity_list_with_metadata(database_name: str) -> list[dict]:
    
    # Initialize an empty list to store the metadata to
    data: list[dict] = []
    
    # Return empty list if database is not found in the Brightway background
    if database_name not in bw2data.databases:
        return []
    
    # Get the data from the background as Brightway object
    database_object: bw2data.Database = bw2data.Database(database_name)
        
    # Loop through each activity in the database
    for act in database_object:
        
        # Extract the metadata
        act_code: str = act.key[0]
        act_name: str = act.get("name")
        act_SimaPro_name: str = act.get("SimaPro_name")
        act_location: str = act.get("location")
        act_unit: str = act.get("unit")
        act_SimaPro_unit: str = act.get("SimaPro_unit")
        act_SimaPro_classification: tuple = act.get("SimaPro_categories", ())
        comment: dict = act.get("simapro metadata", {})
        
        # Add data as dictionary to the list
        data += [{"database": database_name,
                  "activity_code": act_code,
                  "activity_name": act_name,
                  "activity_SimaPro_name": act_SimaPro_name,
                  "activity_location": act_location,
                  "activity_unit": act_unit,
                  "activity_SimaPro_unit": act_SimaPro_unit,
                  "SimaPro_classification": " | ".join(["'" + m + "'" for m in act_SimaPro_classification]),
                  **{"Field_" + k: str(v) for k, v in comment.items()}
                  }]
        
    # Return
    return data


#%% Define function to add unlinked biosphere flows to a (new) database

def add_unlinked_flows_to_biosphere_database(db: bw2io.importers.base_lci.LCIImporter,
                                             biosphere_db_name_unlinked: str,
                                             biosphere_db_name: str,
                                             verbose: bool = True) -> None:
    
    # Make variable check
    hp.check_function_input_type(add_unlinked_flows_to_biosphere_database, locals())
    
    # To overcome Agroscope's anti malware system
    use_batch_approach: bool = True
    
    # Register the new database if not yet existing
    if biosphere_db_name_unlinked not in bw2data.databases:
        bw2data.Database(biosphere_db_name_unlinked).register()
    
    # Get database as bw2data Database object
    db_unlinked: bw2data.Database = bw2data.Database(biosphere_db_name_unlinked)
    
    # Write list of existing biosphere flows, but only the fields extracted
    existing: list[tuple] = [hp.format_values(tuple([v[m] for m in ("name", "top_category", "sub_category", "location", "unit")]),
                                              case_insensitive = True,
                                              strip = True,
                                              remove_special_characters = False) for v in copy.deepcopy(db_unlinked)]
    
    # Retrieve all unlinked biosphere flows
    unlinked_biosphere_flows = [exc for ds in db for exc in ds["exchanges"] if exc["type"] == "biosphere" and not exc.get("input")]
    
    # Make them unique --> remove all duplicates using the unique key feature of dicionaries
    # Also, write the keys to lowercase and strip whitespaces in order to remove the duplicates in the next step
    unique_unlinked_biosphere_flows = {hp.format_values(tuple([exc[m] for m in ("name", "top_category", "sub_category", "location", "unit")]),
                                                        case_insensitive = True,
                                                        strip = True,
                                                        remove_special_characters = False): exc for exc in unlinked_biosphere_flows}
    
    # Remove the unlinked biosphere flows which are already in the database
    unique_unlinked_biosphere_flows_dup_removed = {k: v for k, v in unique_unlinked_biosphere_flows.items() if k not in existing}
    
    # Raise error, if the biosphere database is empty or not found
    if len(list(bw2data.Database(biosphere_db_name))) == 0:
        raise ValueError("Biosphere database '" + str(biosphere_db_name) + "' not existing or empty")
    
    # Extract all keys that should be kept based on an already existing, random biosphere flow
    keep_keys = list(bw2data.Database(biosphere_db_name).random().as_dict().keys())
    
    # Clean the biosphere flow dictionaries so that only fields are kept which are also kept in the existing biosphere
    unlinked_biosphere_flows_cleaned = [{k: v for k, v in exc.items() if k in keep_keys} for _, exc in unique_unlinked_biosphere_flows_dup_removed.items()]
    
    # Adapt or add some fields, e.g. such as the database or the code
    unlinked_biosphere_flows_adapted = [dict(exc, **{"code": str(uuid.uuid4()),
                                                     "type": "natural resource" if exc["categories"][0].lower() in ["raw", "natural resource"] else "emission",
                                                     "exchanges": []}) for exc in unlinked_biosphere_flows_cleaned]
    
    # Simply return if no unlinked flows were found that need to be added
    if len(unlinked_biosphere_flows_adapted) == 0:
        return
    
    # Check if we use the batch approach (True) or the individual approach (False)
    if use_batch_approach:
        
        # Check if the database already exists
        if biosphere_db_name_unlinked in bw2data.databases:
            
            # If yes, we make a copy of it
            db_unlinked: bw2io.importers.base_lci.LCIImporter = copy_brightway_database(db_name = biosphere_db_name_unlinked, new_db_name = biosphere_db_name_unlinked)
        
        else:
            # If not, we simply register a new database importer object
            db_unlinked: bw2io.importers.base_lci.LCIImporter = bw2io.importers.base_lci.LCIImporter(biosphere_db_name_unlinked)
        
        # Add the new data to the existing data
        db_unlinked.data += [{**m, "database": biosphere_db_name_unlinked} for m in unlinked_biosphere_flows_adapted]
        
        # Delete first if already existing
        if biosphere_db_name_unlinked in bw2data.databases:
            del bw2data.databases[biosphere_db_name_unlinked]
        
        # Write the database
        db_unlinked.write_database()
    
    else:
        # Loop through each flow to create newly and add to database
        for bio_dict in unlinked_biosphere_flows_adapted:
            bio = db_unlinked.new_activity(**bio_dict)
            bio.save()
    
    # Print statement on how much activities were linked
    if verbose:
        print("\n------ Unlinked biosphere database update")
        print("Registered {} new unique biosphere flows to '{}'".format(len(unlinked_biosphere_flows_adapted), biosphere_db_name_unlinked))
    
    # Link again
    db.apply_strategy(partial(bw2io.utils.ExchangeLinker.link_iterable_by_fields,
                              other = (m for m in bw2data.Database(biosphere_db_name_unlinked)),
                              fields = ("name", "top_category", "sub_category", "location", "unit"),
                              internal = False,
                              kind = {"biosphere"},
                              relink = False
                              ), verbose = verbose)
      

