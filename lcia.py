import pathlib

if __name__ == "__main__":
    import os
    os.chdir(pathlib.Path(__file__).parent)

import json
import copy
import uuid
import bw2io
import bw2data
import pathlib
import pandas as pd
from functools import partial
import helper as hp
from defaults.categories import (SIMAPRO_BIO_TOPCATEGORIES_MAPPING, SIMAPRO_BIO_SUBCATEGORIES_MAPPING)
from defaults.units import (unit_transformation_mapping,
                            backward_unit_normalization_mapping)
from defaults.locations import (LOCATIONS)
import utils

starting: str = "------------"


#%% LCIA strategies

# Convert categories value to a tuple
def ensure_categories_are_tuples(db_var):
    
    # Make variable check
    hp.check_function_input_type(ensure_categories_are_tuples, locals())
    
    # Loop through each inventory
    for ds in db_var:
        
        # Transform the value of the key 'categories' from the current inventory into a tuple
        if "categories" in ds and not isinstance(ds["categories"], tuple):
            ds["categories"] = tuple(ds["categories"])
            
        # Loop through each exchange
        for exc in ds["exchanges"]:
            
            # Transform the value of the key 'categories' from the current exchange into a tuple
            if "categories" in exc and not isinstance(exc["categories"], tuple):
                exc["categories"] = tuple(exc["categories"])
                
    return db_var



def create_SimaPro_fields(db_var, for_ds: bool, for_exchanges: bool):
    
    for ds in db_var:
        
        if for_ds:
            
            if "SimaPro_name" not in ds:
                if "name" in ds:
                    ds["SimaPro_name"] = ds["name"]
                
            if "SimaPro_categories" not in ds:
                ds["SimaPro_categories"] = None

            if "SimaPro_unit" not in ds:
                if "unit" in ds:
                    ds["SimaPro_unit"] = ds["unit"]
        
        for exc in ds["exchanges"]:
            
            if for_exchanges:
                
                if "SimaPro_name" not in exc:
                    if "name" in exc:
                        exc["SimaPro_name"] = exc["name"]
                    
                if "SimaPro_categories" not in exc:
                    if "categories" in exc:
                        exc["SimaPro_categories"] = exc["categories"]
                    
                if "SimaPro_unit" not in exc:
                    if "unit" in exc:
                        exc["SimaPro_unit"] = exc["unit"]
            
    return db_var


# A copy of the Brightway strategy is made here with the adaptations that we consider our own biosphere mapping
# ... which is slightly different from Brightway but still holds to the ecoinvent standard
def normalize_simapro_biosphere_categories(db_var):
    
    """Normalize biosphere categories to own and ecoinvent standard."""
    
    for ds in db_var:
        for exc in (
            exc for exc in ds.get("exchanges", []) if exc["type"] == "biosphere"
        ):
            cat = SIMAPRO_BIO_TOPCATEGORIES_MAPPING.get(exc["categories"][0], exc["categories"][0])
            if len(exc["categories"]) > 1:
                subcat = SIMAPRO_BIO_SUBCATEGORIES_MAPPING.get(
                    exc["categories"][1], exc["categories"][1]
                )
                exc["categories"] = (cat, subcat)
            else:
                exc["categories"] = (cat,)
    
    return db_var



def transformation_units(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        # If unit and production amount are provided as parameters in the current inventory, we can go on and try to convert the unit, if needed
        if "unit" in ds and "production amount" in ds:
            
            # Lookup the new unit based on the information of the old unit
            unit_transformed_ds = unit_transformation_mapping.get(ds["unit"])
            
            # If a unit transformation has been found, write new data
            if unit_transformed_ds is not None:
                
                # Replace the current with the new unit
                ds["unit"] = unit_transformed_ds["unit_transformed"]
                
                # Adapt the current value to a new value based on the multiplication factor provided
                ds["production amount"] *= unit_transformed_ds["multiplier"] 
                
                # If we transform the current unit, and there is also the field 'SimaPro_unit' present
                # we must also transform that field
                if "SimaPro_unit" in ds:
                    
                    # We try to backward normalize the newly transformed name
                    try:
                        ds["SimaPro_unit"] = backward_unit_normalization_mapping[ds["unit"]]
                        
                    except:
                        # If we fail, we need to raise an error
                        raise ValueError("Inventory unit was transformed using the 'transformation_units' strategy BUT the field 'SimaPro_unit' (" + str(ds["SimaPro_unit"]) + ") could not be adjusted properly for the current inventory (backward mapped).")
        
        # Loop through each exchange and do the same as for the inventories
        for exc in ds.get("exchanges", []):
            
            if "unit" in exc and "amount" in exc:
                
                unit_transformed_exc = unit_transformation_mapping.get(exc["unit"])
                
                if unit_transformed_exc is not None:
                    exc["unit"] = unit_transformed_exc["unit_transformed"]
                    exc["amount"] *= unit_transformed_exc["multiplier"] 
                    
                    # Update negative field
                    if "negative" in exc:
                        exc["negative"] = exc["amount"] < 0
                    
                    # Transform all relevant uncertainty fields
                    exc |= {n: exc[n] * unit_transformed_exc["multiplier"]  for n in ["loc", "shape", "minimum", "maximum"] if n in exc.copy()}
                    
                    # If we transform the current unit, and there is also the field 'SimaPro_unit' present
                    # we must also transform that field
                    if "SimaPro_unit" in exc:
                        
                        # We try to backward normalize the newly transformed name
                        try:
                            exc["SimaPro_unit"] = backward_unit_normalization_mapping[exc["unit"]]
                            
                        except:
                            # If we fail, we need to raise an error
                            raise ValueError("Exchange unit was transformed using the 'transformation_units' strategy BUT the field 'SimaPro_unit' (" + str(exc["SimaPro_unit"]) + ") could not be adjusted properly for the current exchange (backward mapped).")
            
                    
    return db_var




def normalize_and_add_CAS_number(db_var):
    
    """ Brightway2 strategy, which adds CAS number from a mapping file to biosphere elementary flows if no CAS number is yet defined. 

    Parameters
    ----------
    db_var : Brightway2 Backends Pewee Database
        A Brightway2 Backends Pewee Database which should be modified.

    Returns
    -------
    db_var : Modified Brightway2 Backends Pewee Database
        A modified Brightway2 Backends Pewee Database is returned, where CAS numbers are added to biosphere elementary flows, if mapping was successful.

    """
    
    # Make variable check
    hp.check_function_input_type(normalize_and_add_CAS_number, locals())
    
    # -------------------
    # Add CAS number to where no CAS number is currently identified
     
    # Import from JSON
    with open(pathlib.Path(__file__).parent / "defaults" / "CAS.json", "r") as file:
        CAS_mapping_orig: dict = json.load(file)

    # Create a dictionary with key/value pairs, where key is a substance name and value is the respecting CAS-Nr. Make sure to have valid CAS-Nr.s
    CAS_mapping: dict = {k : hp.give_back_correct_cas(v) for k, v in CAS_mapping_orig.items() if hp.give_back_correct_cas(v) is not None}
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through each exchange
        for exc in ds.get("exchanges", []):
            
            # Only add to biosphere flows
            if exc.get("type") == "biosphere":
                
                # Only add if no CAS number is available
                if exc.get("CAS number") is None or exc.get("CAS number") == "" and "name" in exc:
                    
                    # Lookup if a CAS number can be found based on the elementary flow name given
                    CAS_number_1: (str | None) = CAS_mapping.get(exc.get("name", ""))
                    CAS_number_2: (str | None) = CAS_mapping.get(exc.get("name", "").lower())
                    
                    # If a CAS number has been found, add it to the current biosphere flow
                    if CAS_number_1 is not None:
                        exc["CAS number"]: str = CAS_number_1
                        
                    elif CAS_number_2 is not None:
                        exc["CAS number"]: str = CAS_number_2
                    
                    else:
                        exc["CAS number"]: None
                        
                else:
                    # Otherwise, make sure that the existing CAS number is in the correct format and delete if not successfully transformed
                    # Check if transformation yields something
                    if hp.give_back_correct_cas(exc["CAS number"]) is None:
                        
                        # If transformation was unsuccessful and yielded None, add empty string
                        exc["CAS number"]: None = None
                        
                    else:
                        # Otherwise, transform and update the current key/value pair
                        exc["CAS number"] = hp.give_back_correct_cas(exc["CAS number"])
                    
    return db_var


def add_location_to_biosphere_exchanges(db_var,
                                        select_GLO_in_name_valid_for_method_import: bool = False):
    
    """ Add a location parameter to biosphere elementary exchanges in inventories of database 'db_var'.

    Parameters
    ----------
    db_var : Brightway2 Backends Pewee Database
        A Brightway2 Backends Pewee Database where elementary flows should be modified.
        
    select_GLO_in_name_valid_for_method_import : bool
        Should be specified as True, if the strategy is used for the import of impact asssessment methods. Otherwise, set this parameter to False, if e.g., inventories are imported.
        
        Explanation: there might appear flows in impact assessment methods which have 'GLO' specified in the flow name AND at the same time the same flow name without 'GLO' in the name also appears.
        In this case, we can only keep one flow, otherwise we would have duplicated flows. The strategy eliminates the flow where 'GLO' was not specified in the name and keeps the flow where 'GLO' was specified in the name.

    Returns
    -------
    db_var : Modified Brightway2 Backends Pewee Database
        A modified Brightway2 Backends Pewee Database is returned, where the parameter 'location' is added to each biosphere elementary exchange.

    """
    
    # Check function input type
    hp.check_function_input_type(add_location_to_biosphere_exchanges, locals())

    # Additional location mappings which might appear in biosphere flows
    # and which might be outdated and need to be replaced with other locations
    additional_location_mappings = {"ASCC": "US-ASCC",
                                    # "FRCC": "",
                                    "Europe, without Russia and Turkey": "Europe, without Russia and Türkiye",
                                    "HICC": "US-HICC",
                                    "MRO, US only": "US-MRO",
                                    "NPCC, US only": "US-NPCC",
                                    "OCE": "UN-OCEANIA",
                                    # "OECD": "",
                                    "RFC": "US-RFC",
                                    "SERC": "US-SERC",
                                    "TRE": "US-TRE",
                                    "WECC, US only": "US-WECC",
                                    # "ZR": "",
                                    }

    # Check with the current location mapping, if the mapped locations appear
    # If not, raise an error. In that case, adjust the mapping above
    mapped_locations_not_available = [v for k, v in additional_location_mappings.items() if LOCATIONS.get(v) is None]
    if mapped_locations_not_available != []:
        raise ValueError("Additional location mapping (variable 'additional_location_mappings') contains key/value pairs where the value (= mapped location) does not appear in the 'location_mapping'. Make sure that the mapping is valid = that the value appears in the 'location_mapping' --> replace the following values:\n- " + "\n- ".join(mapped_locations_not_available))
        
    # Valid ecoinvent geographies
    locations = list(LOCATIONS.keys()) + list(additional_location_mappings.keys())
    
    # Make the own location mapping keys lowercase
    additional_location_mappings_small = {k.lower(): v for k, v in additional_location_mappings.items()}
    
    # Create dictionary for better search performance
    locations_dict = {m: m for m in locations}
    
    
    
    # Function to split exchange name into name and location based on fragment specified
    def split_exchange_name(name: str, pattern: str, loc_mapping_dict: dict):
        
        # Check function input type
        hp.check_function_input_type(split_exchange_name, locals())
        
        # Split the name with the pattern specified into fragments
        splitted = name.split(pattern)
        
        # Initialise variables
        initial = splitted[len(splitted) - 1]
        appended = (initial,)
        
        # Go through each fragment which was split by the pattern
        # ... and extract potential locations
        for mm in reversed(splitted[:-1]):
            appended += (mm + pattern + initial,)
            initial = mm + pattern + initial
        
        # Check if the fragment which could be locations are actually locations or not by comparing the fragment with the location mapping dictionary
        locs_extracted = [loc_mapping_dict[mmm] for mmm in reversed(appended) if loc_mapping_dict.get(mmm) is not None]
        
        # If something was found, return the result
        if len(locs_extracted) > 0:
            
            # Return a successful boolean, the new name and the new location
            return True, name.replace(pattern + locs_extracted[0], ""), locs_extracted[0]
        
        else:
            # Return an unsuccessful boolean, the old name and a global location
            return False, name, "GLO"



    # Loop through each inventory
    for ds in db_var:
        
        # Initalize list to store elementary flows, which have the pattern 'GLO' in their name
        GLO_priorized_orig = []
        
        # Loop through all exchanges of an inventory.
        for exc in ds["exchanges"]:
            
            # Only go on if the exchange is a biosphere elementary flow
            if exc.get("type") == "biosphere":
                
                # Check if location key is already available
                if exc.get("location") is not None:
                    
                    # Add SimaPro name field
                    # Either with the comma and the location abbreviation in the name
                    if "SimaPro_name" not in exc and exc["location"] != "GLO":
                        exc["SimaPro_name"] = exc["name"] + ", " + str(exc["location"])
                    
                    # Or without the location abbreviation and only the name, if the location is GLO
                    elif "SimaPro_name" not in exc and exc["location"] == "GLO":
                        exc["SimaPro_name"] = exc["name"]
                        
                    continue
                    
                    
                # Apply the first pattern and extract new name and new location
                successful_1, name_1, location_1 = split_exchange_name(exc["name"], ", ", locations_dict)
                
                # If the first pattern did not yield a result, try to apply the second pattern
                if not successful_1:
                    
                    # Apply the second pattern and extract new name and new location
                    successful_2, name_2, location_2 = split_exchange_name(exc["name"], ",", locations_dict)
                    
                else:
                    # Otherwise just specify a false boolean
                    successful_2 = False
                
                # Add new name and new location extracted with the first pattern to the exchange
                if successful_1:
                    
                    # Add parameters to exchange dictionary
                    exc["SimaPro_name"] = exc["name"]
                    exc["location"] = additional_location_mappings_small.get(location_1.lower(), location_1)
                    exc["name"] = name_1
                    
                    # Check, if the pattern 'GLO' has appeared in the elementary flow name
                    # If yes, store the flow in a list. In case the same flow without specifying 'GLO' in the name appears in the same method,
                    # it will be overwritten with that elementary flow at the end
                    if exc["location"] == "GLO" and select_GLO_in_name_valid_for_method_import:
                        
                        # Add the current elementary flow to the list
                        GLO_priorized_orig += [exc].copy()
                
                # Add new name and new location extracted with the second pattern to the exchange
                elif successful_2:
                    
                    # Add parameters to exchange dictionary
                    exc["SimaPro_name"] = exc["name"]
                    exc["location"] = additional_location_mappings_small.get(location_2.lower(), location_2)
                    exc["name"] = name_2
                    
                    # Check, if the pattern 'GLO' has appeared in the elementary flow name
                    # If yes, store the flow in a list. In case the same flow without specifying 'GLO' in the name appears in the same method,
                    # it will be overwritten with that elementary flow at the end
                    if exc["location"] == "GLO" and select_GLO_in_name_valid_for_method_import:
                        
                        # Add the current elementary flow to the list
                        GLO_priorized_orig += [exc].copy()
                    
                else:
                    # Add parameters to exchange dictionary
                    exc["SimaPro_name"] = exc["name"]
                    exc["location"] = additional_location_mappings_small.get(location_1.lower(), location_1)
                    exc["name"] = name_1

        
        # Check if flows have appeared, where 'GLO' has been specified in the elementary flow name
        if select_GLO_in_name_valid_for_method_import and GLO_priorized_orig != []:
            
            # Check if 'location' is specified as separate key in exchanges
            if None in [m if "location" in m else None for m in GLO_priorized_orig]:
                
                # Make a dictionary of the list with unique values as keys
                # ... using 'name', 'categories' and 'unit'
                GLO_priorized = {(m["name"], m["categories"], m["unit"]): m for m in GLO_priorized_orig}
                
                # Delete all unique and same exchanges as in the list 'GLO_priorized'
                ds["exchanges"] = [m for m in ds["exchanges"].copy() if not any([element is None for element in [m.get("name"), m.get("categories"), m.get("unit")]]) and (m.get("name"), m.get("categories"), m.get("unit")) not in GLO_priorized.keys()].copy()
            
            else:
                # Make a dictionary of the list with unique values as keys
                # ... using 'name', 'categories', 'unit' and 'location'
                GLO_priorized = {(m["name"], m["categories"], m["unit"], m["location"]): m for m in GLO_priorized_orig}
                
                # Delete all unique and same exchanges as in the list 'GLO_priorized'
                ds["exchanges"] = [m for m in ds["exchanges"].copy() if not any([element is None for element in [m.get("name"), m.get("categories"), m.get("unit"), m.get("location")]]) and (m.get("name"), m.get("categories"), m.get("unit"), m.get("location")) not in GLO_priorized.keys()].copy()
            
            # Add only the flows again, which have been specified by 'GLO' in the name
            ds["exchanges"] += [n for n in GLO_priorized.values()].copy()
        
    return db_var



def add_top_and_subcategory_fields_for_biosphere_flows(db_var, remove_initial_category_field: bool = False):
    
    for ds in db_var:
        for exc in ds["exchanges"]:
            
            if exc["type"] == "biosphere":
                
                exc["top_category"] = exc["categories"][0]
                exc["sub_category"] = exc["categories"][1] if len(exc["categories"]) > 1 else ""
                
                if remove_initial_category_field:
                    del exc["categories"]
                    
    return db_var


def add_code_field(db_var, mapping: dict, identifying_fields: tuple = ("name", "categories", "unit", "location")):
    
    for ds in db_var:
        for exc in ds["exchanges"]:
            
            if "code" in exc:
                continue
            
            exc_ID = hp.format_values(tuple([exc[m] for m in identifying_fields]),
                                      case_insensitive = True,
                                      strip = True,
                                      remove_special_characters = False)
            
            exc["code"] = mapping[exc_ID]["code"]
            
    return db_var

    

# Nach add_code_field
def add_top_category_factors_as_proxy_for_sub_categories(db_var, biosphere_dict: dict):

    mapping_bio = {}
    for k, v in biosphere_dict.items():
        ID_bio_I = (v["name"], v["top_category"], v["unit"], v["location"])
        ID_bio_II = (v["name"], v["top_category"], v["sub_category"], v["unit"], v["location"])
        
        if v["sub_category"] != "":
            
            if ID_bio_I not in mapping_bio:
                mapping_bio[ID_bio_I] = {ID_bio_II: v}
            else:
                mapping_bio[ID_bio_I][ID_bio_II] = v
    
    
    
    for ds in db_var:
        
        exc_copy = copy.deepcopy(ds["exchanges"])
        available = {(m["name"], m["top_category"], m["sub_category"], m["unit"], m["location"]): True for m in exc_copy if m["sub_category"] != ""}
        amounts = {(m["name"], m["top_category"], m["unit"], m["location"]): m["amount"] for m in exc_copy if m["sub_category"] == ""}
        seen = {}
        exchanges_to_add = []
        
        for exc in ds["exchanges"]:
            
            exc_ID_I = (exc["name"], exc["top_category"], exc["unit"], exc["location"])
            
            if seen.get(exc_ID_I, False):
                continue
            else:
                seen[exc_ID_I] = True
            
            additions_to_check = mapping_bio.get(exc_ID_I)
            
            if additions_to_check is None:
                continue
            
            for addition_ID, addition in additions_to_check.items():
                
                if available.get(addition_ID, False):
                    continue
                
                if addition["sub_category"] == "":
                    raise ValueError("Top category would be added but should NOT.")
                
                # Check if characterization factor of top category is available.
                # If not, we can not add anything else for the sub categories
                amount_of_top_category = amounts.get(exc_ID_I)
                
                # Only go on if a factor was found. Otherwise, go to next value
                if amount_of_top_category is not None:
                    exchange_to_add = {k: v for k, v in addition.copy().items() if k not in ["type", "database", "exchanges"]}
                    exchange_to_add["amount"] = amount_of_top_category
                    exchange_to_add["type"] = "biosphere"
                    exchanges_to_add += [exchange_to_add]
            
        ds["exchanges"] = copy.deepcopy(exc_copy + exchanges_to_add)
    
    return db_var



def append_missing_regionalized_flows_to_methods(biosphere_standardized: dict,
                                                 logs_output_path: pathlib.Path,
                                                 verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(append_missing_regionalized_flows_to_methods, locals())
    
    # Print message
    if verbose:
        print(starting + "Append missing regionalized flows to methods")
    
    # Make sure that registered methods include all regionalized flows
    # Initialize list to store not available global factors
    global_factors_not_available = []

    # Initialize list to log the changes in the methods and in the flows (= detailed method change logger)
    method_change_logger = []
    method_change_logger_detailed = []

    # Initialize empty dictionaries
    regionalized_flows = {}
    keys_with_GLO_factor = {}

    # Loop through all flows
    # Non-regionalized flows are identified by name, categories and unit, which is used as flow ID here
    # Flows with GLO as location are used as characterization factor proxy if no regionalization is available for the flow
    for k, v in biosphere_standardized.items():
        
        # Flow ID
        flow_identifier = (v["name"], v["categories"], v["unit"])
        
        # If the current flow has the region GLO, save the input in the dictionary to use it later as characterization factor
        if v["location"] == "GLO":
            keys_with_GLO_factor[flow_identifier] = k
        
        # Add the current input of the flow to the dictionary
        if flow_identifier not in regionalized_flows:
            regionalized_flows[flow_identifier] = [k]
        else:
            regionalized_flows[flow_identifier] += [k]

    # All LCIA method names available
    met = list(bw2data.methods)

    # Initialize variable which counts, how many methods were changed
    counter = 0

    # Loop through each method registered beforehand
    for method_tuple in met:
        
        # Extract the LCIA method meta data to dictionary
        method_dict = copy.deepcopy(bw2data.Method(method_tuple).metadata)
        
        # Extract the number of characterization factors existent in the current method
        length_exchanges_before = len(bw2data.Method(method_tuple).load())
        
        # Initialize a new list
        new_method_exchanges = []
        
        # Create a mappig dictionary of the characterization factor of the current method
        existing_factors_dict = copy.deepcopy({key: cf for key, cf in bw2data.Method(method_tuple).load()})
        
        # Extract all flow ID's that appear in the method exchanges
        needed_flows = set([(biosphere_standardized[key]["name"],
                             biosphere_standardized[key]["categories"],
                             biosphere_standardized[key]["unit"]) for key in list(existing_factors_dict.keys())])
        
        # Loop through each flow ID
        for flow_ID_tuple in needed_flows:
            
            # Extract the global characterization factor for the current flow ID
            # This factor will be used, in case no characterization factor is found
            if existing_factors_dict.get(keys_with_GLO_factor.get(flow_ID_tuple, "")) is not None:
                global_factor = existing_factors_dict[keys_with_GLO_factor[flow_ID_tuple]]
            else:
                # raise ValueError("No global factor available for flow: " + str(flow_ID_tuple) + " in method " + str(method_tuple))
                found_factors = [existing_factors_dict[m] for m in regionalized_flows[flow_ID_tuple] if existing_factors_dict.get(m) is not None]
                global_factor = sum(found_factors) / len(found_factors)
                global_factors_not_available += [{"method": method_tuple, "flow_ID_tuple": flow_ID_tuple, "number_cf_used_for_mean": len(found_factors), "proxy_global_factor": global_factor}]
                
            # Extract all flows for the current flow ID
            all_flows = regionalized_flows[flow_ID_tuple]
            
            # Append the flows and their respective characterization factors to the new list of characterization factors
            new_method_exchanges += [(m, existing_factors_dict.get(m, global_factor)) for m in all_flows]
            
            # Write to detailed method change logger
            method_change_logger_detailed += [{"flow_name": biosphere_standardized[m]["name"], 
                                               "flow_categories": biosphere_standardized[m]["categories"],
                                               "flow_unit": biosphere_standardized[m]["unit"],
                                               "flow_location": biosphere_standardized[m]["location"],
                                               "method": method_tuple,
                                               "changed": True} for m in all_flows if m not in existing_factors_dict]
        
        # Extract the number of characterization factors after having corrected the method
        length_exchanges_after = len(new_method_exchanges)
        
        # Make validation and print to console
        if length_exchanges_before > length_exchanges_after:
            
            # Raise an error, if the number of characterization factor has decreased in comparison to the original method
            raise ValueError("Flows have been removed --> should not be. Check method " + str(method_tuple))
        
        elif length_exchanges_before == length_exchanges_after:
            
            # Write logger
            method_change_logger += [{"method": method_tuple, "changed": False, "number_of_cf_orig": length_exchanges_before}]
            continue
        else:
            
            # print("\n" + str(method_tuple) + " --> changed\n(" + str(length_exchanges_before) + " exchanges before, " + str(length_exchanges_after) + " exchanges after)")

            # Write logger
            method_change_logger += [{"method": method_tuple, "changed": True, "number_of_cf_orig": length_exchanges_before, "number_of_cf_after_change": length_exchanges_after}]
            
            # Raise counting variable
            counter += 1

        # Delete method if already existing
        if method_tuple in bw2data.methods:
            del bw2data.methods[method_tuple]
        
        # Register the corrected method
        method_corrected = bw2data.Method(copy.deepcopy(method_tuple))
        method_corrected.register()
        
        # Add completed (= corrected) list of flows to the registered method
        method_corrected.write(copy.deepcopy(new_method_exchanges))
        
        # Add metadata
        # ... method unit
        bw2data.methods[method_tuple]["unit"] = method_dict["unit"]
        
        # ... method description (currently empty)
        bw2data.methods[method_tuple]["description"] = method_dict["description"]
        
        # Flush data
        bw2data.methods.flush()

    
    # Print statement
    if verbose:
        print(str(counter) + " methods were changed\n")
    
    if len(method_change_logger_detailed) > 0:
    
        # Summarize
        df_method_change_logger_detailed = pd.DataFrame(method_change_logger_detailed).groupby(["flow_name", "method", "changed"]).size().reset_index(name = "amount_of_flows_added")
        df_method_change_logger_detailed.to_excel(logs_output_path / "Flow_names_added_to_methods.xlsx")

    # Write to loggers to XLSX
    pd.DataFrame(global_factors_not_available).to_excel(logs_output_path / "Methods_where_global_CF_factors_not_available.xlsx")
    pd.DataFrame(method_change_logger).to_excel(logs_output_path / "Amount_of_CFs_added_to_methods.xlsx")
    
    # Print statement
    if verbose:
        print("Check the following folder for the logging files:\n" + str(logs_output_path) + "\n")



#%% Import functions

# Add LCIA methods which rely on weighting, damage and/or normalization factors
def add_damage_normalization_weighting(original_method: tuple,
                                       normalization_factor: (float | int | None),
                                       weighting_factor: (float | int | None),
                                       damage_factor: (float | int | None),
                                       new_method: tuple,
                                       new_method_unit: str,
                                       new_method_description: (str | None),
                                       verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(add_damage_normalization_weighting, locals())
    
    if new_method in bw2data.methods:
        del bw2data.methods[new_method]
    
    if original_method not in bw2data.methods:
        raise ValueError("Original method '{}' not registered in the background. Use 'bw2data.methods' to check which methods are available.".format(original_method))
    
    normalization_factor: float = float(normalization_factor) if normalization_factor is not None else float(1)
    weighting_factor: float = float(weighting_factor) if weighting_factor is not None else float(1)
    damage_factor: float = float(damage_factor) if damage_factor is not None else float(1)

    # Print statement
    if verbose:
        print(starting + "Add damage, normalization and weighting factors from method '{}' and create new method '{}'".format(original_method, new_method))
        print()
    
    new_exchanges: dict = {}
    
    # Read in current characterization factors from 'FROM_method' and add the damage, normalization and weighting factor of the current row
    # Append list to the list initialized before
    for key, cf in bw2data.Method(original_method).load():
        
        if key not in new_exchanges:
            new_exchanges[key]: float = float(cf) * normalization_factor * weighting_factor * damage_factor
        
        else:
            new_exchanges[key] += float(cf) * normalization_factor * weighting_factor * damage_factor

    # Convert from dictionary to list
    exchanges = [(k, v) for k, v in new_exchanges.copy().items()]
    
    # Register a new method called 'TO_method'
    method_new = bw2data.Method(new_method)
    method_new.register()
    
    # Add new characterization factors to the registered method
    method_new.write(exchanges.copy())
    
    # Add metadata
    # ... method unit
    bw2data.methods[new_method]["unit"] = new_method_unit
    
    # ... method description (currently empty)
    bw2data.methods[new_method]["description"] = new_method_description
    
    # Flush data
    bw2data.methods.flush()



def add_excluded_longterm_method(original_method: (tuple | list[tuple] | None) = None,
                                 method_string_to_be_added: str = "no LT",
                                 verbose: bool = True) -> None:
    
    all_methods: list[str] = list(bw2data.methods)
    
    if original_method is None:
        method_list: list[str] = all_methods
        
    elif isinstance(original_method, tuple):
        method_list: list[str] = [original_method]
    
    elif isinstance(original_method, list):
        method_list: list[str] = original_method
    
    if verbose:
        print("------------- Adding no long-term LCIA methods")
    
    for method in method_list:
        
        if method not in all_methods:
            raise ValueError(f"Method '{method}' is not registered in Brightway. " \
                             "Thus, can not construct and add 'no longterm' LCIA method.")
        
        no_lt_method_name: tuple[str] = method + (method_string_to_be_added,)
        
        if no_lt_method_name in all_methods:
            del bw2data.methods[no_lt_method_name]
        
        cfs: list[tuple[tuple[str, str], float]] = bw2data.Method(method).load()
        
        at_least_one_exchange_set_to_0: bool = False
        new_cfs: list[tuple] = []
        
        # Set 
        for (db, ID), cf in cfs:
            categories: (tuple | None) = bw2data.Database(db).get(ID).get("categories")
            
            if categories is None:
                raise ValueError("Could not find 'categories' for biosphere flow " \
                                 f"'{(db, ID)}'.")
            
            sub_cat: str = categories[1] if len(categories) > 1 else ""
            is_longterm: bool = "longterm" in sub_cat or "long-term" in sub_cat
            
            if is_longterm:
                new_cfs += [((db, ID), 0.0)]
                at_least_one_exchange_set_to_0: bool = True
                
            else:
                new_cfs += [((db, ID), cf)]
        
        
        if at_least_one_exchange_set_to_0:
            
            # Register a new method
            method_new = bw2data.Method(no_lt_method_name)
            method_new.register()
            
            # Add new characterization factors to the registered method
            method_new.write(new_cfs)
            
            # Add metadata
            # ... method unit
            bw2data.methods[no_lt_method_name]["unit"] = (
                bw2data.methods[method]["unit"]    
            )
            
            # ... method description
            bw2data.methods[no_lt_method_name]["description"] = (
                f"Characterization factors for long-term emissions (subcompartment " \
                "containing a sring like 'long-term') set to 0.\n\n" \
                f"{bw2data.methods[method].get('unit', '')}"
            )
            
            # Flush data
            bw2data.methods.flush()
            
            if verbose:
                print(f" - {no_lt_method_name}")
    
    if verbose:
        print()
        

# Extract the biosphere flows, method names and duplicated flows and export to XLSX
def write_biosphere_flows_and_method_names_to_XLSX(biosphere_db_name: str,
                                                   output_path: pathlib.Path,
                                                   verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(write_biosphere_flows_and_method_names_to_XLSX, locals())
    
    # Print statement
    if verbose:
        print(starting + "Write biosphere flows and LCIA method names to Excel")

    # Extract all flows and write to 'biosphere_orig'
    biosphere_orig: list[dict] = [m.as_dict() for m in bw2data.Database(biosphere_db_name)]

    # Specify the cols which make the flows unique
    # Depending whether regionalized flows exist or not
    group_cols = ("name", "categories", "unit", "location") + ("type", "CAS number",)
    
    # Remove the duplicates based on the columns specified
    biosphere_df = pd.DataFrame(biosphere_orig).drop_duplicates(group_cols)
    biosphere_df.to_excel(output_path / "Biosphere_elementary_flows.xlsx")
    
    # Print statement
    if verbose:
        print("Table with biosphere flows saved to:\n" + str(output_path / "Biosphere_elementary_flows.xlsx") + "\n")
    
    # Check if there are duplicates in the biosphere
    table = pd.DataFrame({m: [n[m] for n in biosphere_df.to_dict("records")] for m in ("name", "categories", "unit", "location")})
    duplicates = table[table.duplicated()]

    # Check if there are duplicated elementary flows
    if not duplicates.empty:
    
        # Write excel table with duplicated elementary flows
        duplicates.to_excel(output_path / "Duplicated_flows_in_biosphere3.xlsx")
    
        # If yes, raise error
        raise ValueError("There are duplicates in the database '" + biosphere_db_name + "'. Check file 'Duplicated_flows_in_biosphere.xlsx' to see which flows are duplicated.")
        
    # Export the names of the current methods registered
    # Export current methods to list
    pd.DataFrame({"LCIA_method_names": [m for m in bw2data.methods]}).to_excel(output_path / "Available_LCIA_method_names.xlsx")
    
    # Print statement
    if verbose:
        print("Table with LCIA method names saved to:\n" + str(output_path / "Available_LCIA_method_names.xlsx") + "\n")
    


def register_biosphere(Brightway_project_name: str,
                       BRIGHTWAY2_DIR: pathlib.Path,
                       biosphere_db_name: str,
                       imported_methods: list,
                       verbose: bool = True) -> dict:
    
    # Make variable check
    hp.check_function_input_type(register_biosphere, locals())
    
    # Switch Brightway2 project directory path
    utils.change_brightway_project_directory(BRIGHTWAY2_DIR, verbose)
    
    # Open Brightway2 project
    bw2data.projects.set_current(Brightway_project_name)
    
    # Delete first if already existing
    if biosphere_db_name in bw2data.databases:
        
        # Print statement
        if verbose:
            print(starting + "Delete biosphere database:\n" + biosphere_db_name)
        
        # Delete
        del bw2data.databases[biosphere_db_name]
        
        # Print statement
        if verbose:
            print()
        
    
    # Print statement
    if verbose:
        print(starting + "Data is imported into project:\n" + Brightway_project_name + "\n")
        
    # Initialize an empty dictionary to store all unique biosphere flows used in the LCIA methods previously imported
    biosphere_mapping: dict = {}
    
    # Loop through each method and subsequently through each characterization factor of the method to extract the biosphere flow
    # Loop through each method
    for imported_method in copy.deepcopy(imported_methods):
        
        # Loop through each biosphere flow
        for flow in imported_method["exchanges"]:
            
            # For the biosphere database, we don't need to keep the amount field, so we can delete it
            del flow["amount"]
            
            # Usually, biosphere flows are unique by name, categories and unit. However, we extracted a 'location' field from the name, therefore there are also unique by location
            # We extract the ID tuple, that means we construct for each flow an ID by the 'identifying_fields' (name, categories, unit, location) 
            flow_ID = hp.format_values(tuple([flow[m] for m in ("name", "categories", "unit", "location")]),
                                       case_insensitive = True,
                                       strip = True,
                                       remove_special_characters = False)
            
            # We add the flow to the mapping. In case the ID is already there, it will be overwritten which is of no problem.
            # We also add some more fields -->
            # ... for biosphere flows, the type needs to be 'emission' or 'natural resource'
            # ... we need to add the biosphere database name
            # ... a unique code is needed for each flow, which we construct individually
            # ... biosphere flows per default have no exchanges, therefore we add an empty list
            biosphere_mapping[flow_ID] = dict(flow, **{"type": "natural resource" if flow["top_category"].lower() in ["raw", "natural resource"] else "emission",
                                                       "database": biosphere_db_name,
                                                       "code": str(uuid.uuid4()),
                                                       "exchanges": []})
                
        
    # Brightway only allows a specific format to be written to databases
    # We need to make a dictionary with the code and database parameter as tuple as key and the flow as dictionary as value
    biosphere_dict = {(v["database"], v["code"]): v for k, v in biosphere_mapping.items()}
    
    # Print statement
    print("\n" + starting + "Writing biosphere flows to Brightway database")
    
    # Deepcopy
    deepcopied_biosphere_dict: dict = copy.deepcopy(biosphere_dict)
    
    # ... and write biosphere flows to a new biosphere database
    bw2data.Database(biosphere_db_name).write(deepcopied_biosphere_dict)
    
    # Configurate biosphere_db_name as the biosphere database
    bw2data.config.p["biosphere_database"] = biosphere_db_name


def import_SimaPro_LCIA_methods(path_to_SimaPro_CSV_LCIA_files: pathlib.Path,
                                encoding: str = "latin-1",
                                delimiter: str = "\t",
                                verbose: bool = True,
                                ) -> list:
    
    # Make variable check
    hp.check_function_input_type(import_SimaPro_LCIA_methods, locals())

    # ... filenames of CSV's which should be imported
    list_of_SimaPro_method_CSV_filepaths: list[pathlib.Path] = [m for m in path_to_SimaPro_CSV_LCIA_files.iterdir() if m.suffix.lower() == ".csv"]
    
    if list_of_SimaPro_method_CSV_filepaths == []:
        raise ValueError("No SimaPro LCIA files found in path:\n{}".format(path_to_SimaPro_CSV_LCIA_files))
    
    # Initialize list to store all methods to
    imported_methods = []
    
    # Print statement
    if verbose:
        print(starting + "Importing SimaPro LCIA methods:")
    
    # Loop through each method file individually and import the method using the Brightway importer
    for filepath in list_of_SimaPro_method_CSV_filepaths:
        
        # Print where we are
        if verbose:
            print(filepath.name)
        
        # Read the SimaPro CSV file using the Brightway importer
        # Add the imported method directly to the list
        imported_methods += bw2io.extractors.SimaProLCIACSVExtractor.extract(str(filepath), delimiter, encoding)
        
    # Print statement
    if verbose:
        print("\n" + starting + "Apply strategies")    
    
    # Apply strategies to adapt the methods just imported
    # ... make sure that all categories fields of all exchange flows (here = biosphere flows) are of type tuple
    if verbose:
        print("Applying strategy: ensure_categories_are_tuples")
    imported_methods = ensure_categories_are_tuples(copy.deepcopy(imported_methods))
    
    # ... add more fields to each exchange dictionary --> we want to keep the SimaPro standard
    if verbose:
        print("Applying strategy: create_SimaPro_fields")
    imported_methods = create_SimaPro_fields(copy.deepcopy(imported_methods), for_ds = False, for_exchanges = True)
    
    # ... to each exchange, add a key/value pair 'type: 'biosphere''
    if verbose:
        print("Applying strategy: set_biosphere_type")
    imported_methods = bw2io.strategies.lcia.set_biosphere_type(copy.deepcopy(imported_methods))
    
    # ... we remove the second category (= sub_category) of the categories field if it is unspecified
    if verbose:
        print("Applying strategy: drop_unspecified_subcategories")
    imported_methods = bw2io.strategies.biosphere.drop_unspecified_subcategories(copy.deepcopy(imported_methods))
        
    # ... we use the new ecoinvent names for the categories. Brightway specifies a mapping for that
    if verbose:
        print("Applying strategy: normalize_simapro_biosphere_categories")
    imported_methods = normalize_simapro_biosphere_categories(copy.deepcopy(imported_methods))
        
    # ... we do the same as for the normalization of the categories also for the normalization of units
    # this means, we use the brightway mapping to normalize 'kg' to 'kilogram' for instance
    if verbose:
        print("Applying strategy: normalize_units")
    imported_methods = bw2io.strategies.generic.normalize_units(copy.deepcopy(imported_methods))
    
    # ... at the end, we try to transform all units to a common standard, if possible
    # 'kilowatt hour' and 'kilojoule' are for example both transformed to 'megajoule' using a respective factor for transformation
    if verbose:
        print("Applying strategy: transformation_units")
    imported_methods = transformation_units(copy.deepcopy(imported_methods))
    
    # ... SimaPro contains regionalized flows. But: the country is only specified within the name of a flow. That is inconvenient
    # we extract the country/region of a flow (if there is any) from the name and write this information to a separate field 'location'
    # flows where no region is specified obtain the location 'GLO'
    if verbose:
        print("Applying strategy: add_location_to_biosphere_exchanges")
    imported_methods = add_location_to_biosphere_exchanges(copy.deepcopy(imported_methods), True)
    
    if verbose:
        print("Applying strategy: add_top_and_subcategory_fields_for_biosphere_flows")
    imported_methods = add_top_and_subcategory_fields_for_biosphere_flows(copy.deepcopy(imported_methods))
    
    # Normalize and add a CAS number from a mapping, if possible
    imported_methods = normalize_and_add_CAS_number(copy.deepcopy(imported_methods))
    
    if verbose:
        print()
        
    return imported_methods
    

def register_SimaPro_LCIA_methods(imported_methods: list,
                                  biosphere_db_name: str,
                                  Brightway_project_name: str,
                                  BRIGHTWAY2_DIR: pathlib.Path,
                                  logs_output_path: pathlib.Path,
                                  append_missing_regionalized_flows: bool = True,
                                  verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(register_SimaPro_LCIA_methods, locals())
    
    # Switch Brightway2 project directory path
    utils.change_brightway_project_directory(BRIGHTWAY2_DIR, verbose)
    
    # Open Brightway2 project
    bw2data.projects.set_current(Brightway_project_name)
    
    if biosphere_db_name not in bw2data.databases:
        raise ValueError("Biosphere database with the name '{}' not found/not registered in the Brightway background. Available databases are:\n - {}".format(biosphere_db_name, "\n - ".join(bw2data.databases)))
    
    # Delete methods if already existing
    method_names: list[tuple[str]] = [m["name"] for m in imported_methods]
    for method_name in method_names:
        if method_name in bw2data.methods:
            del bw2data.methods[method_name]
            print("Deleted LCIA method '{}'".format(method_name))
    
    biosphere_list: list = [m.as_dict() for m in bw2data.Database(biosphere_db_name)]
    biosphere_dict: dict = {(m["database"], m["code"]): m for m in biosphere_list}
    biosphere_mapping: dict = {hp.format_values(tuple([m[n] for n in ("name", "categories", "unit", "location")]),
                               case_insensitive = True,
                               strip = True,
                               remove_special_characters = False): m for m in biosphere_list}

    # ... with SimaPro, we need to link by top and sub category individually for biosphere flows
    # this is not possible, if we have only one field which combines both categories
    # Therefore, we write the categories field into two separate fields, one for top category and one for sub category
    if verbose:
        print("\n" + "Applying strategy: add_top_category_factors_as_proxy_for_sub_categories")
    imported_methods = add_top_category_factors_as_proxy_for_sub_categories(imported_methods,
                                                                            biosphere_dict = biosphere_dict)

    # Currently, it is somehow only possible to link the biosphere flows (just written) by the code field (at least to my experience).
    # For other databases, 'link_iterable_by_fields' can use various fields to perform the linking on.
    # Therefore, we first need to add the codes given to the biosphere flows when writing the biosphere databases manually to each flow in the imported method
    # We do that by using a specific function/strategy which uses the biosphere_mapping constructed beforehand
    # We go through each flow in the method, extract the ID of the flow and compare it to the biosphere_mapping
    if verbose:
        print("Applying strategy: add_code_field")
    imported_methods = add_code_field(copy.deepcopy(imported_methods),
                                      mapping = biosphere_mapping,
                                      identifying_fields = ("name", "categories", "unit", "location"))
    
    # We are now able to open a new LCIA importer object
    methods = bw2io.importers.base_lcia.LCIAImporter("", biosphere = biosphere_db_name)
    
    # We write the data of our methods to the importer object
    methods.data = copy.deepcopy(imported_methods)
    
    # We apply the linking between the imported methods and the biosphere database (by field 'code')
    methods.apply_strategy(partial(bw2io.strategies.generic.link_iterable_by_fields,
                                   other = (obj for obj in bw2data.Database(biosphere_db_name)),
                                   fields = ["code"]
                                   ), verbose = verbose)
    
    # And we finally write the LCIA importer object to the brightway background
    if verbose:
        print("\n" + starting + "Writing LCIA methods to Brightway")
    methods.write_methods(overwrite = True,
                          verbose = verbose)
    if verbose:
        print("")
    
    # For each registered LCIA method (which we did just before), we need to check if for each flow in the method, all regionalized versions of that flow have been specified
    # Why? Because if not, we would possibly underestimate the environmental impact in case a regionalized flow is not catched by the method
    # We loop through each LCIA method registered (from the background) and compare all biosphere flows in there with the biosphere database.
    # In case there are flows with the same name but different region which have not yet been added to the methods, they will be added by using the factor for 'GLO'
    if append_missing_regionalized_flows:
        append_missing_regionalized_flows_to_methods(biosphere_standardized = biosphere_dict,
                                                     logs_output_path = logs_output_path,
                                                     verbose = verbose)
    


# Copied and adapted from the Brightway ecoinvent 'get_ecoinvent_release' function
def import_XML_LCIA_methods(XML_LCIA_filepath: pathlib.Path,
                            biosphere_db_name: str,
                            ecoinvent_version: (str | None) = None):
    
    # hp.check_function_input_type(import_XML_LCIA_methods, locals())
    dfs: dict = pd.read_excel(XML_LCIA_filepath, sheet_name = None)
    units_mapping: dict = {(row["Method"], row["Category"], row["Indicator"]): row["Indicator Unit"] for idx, row in dfs["Indicators"].iterrows()}
    
    mapping: dict = {}
    for flow in bw2data.Database(biosphere_db_name):
        mapping[(flow["name"],) + tuple(flow["categories"])] = flow.key
        
        if flow["name"].startswith("[Deleted]"):
            mapping[(flow["name"].replace("[Deleted]", ""),) + tuple(flow["categories"])] = flow.key
    
    def drop_unspecified(a: str, b: str, c: str) -> tuple:
        if c.lower() == "unspecified":
            return (a, b)
        else:
            return (a, b, c)
    
    lcia_data: dict = {}
    for idx, row in dfs["CFs"].replace({float("NaN"): None}).iterrows():
        impact_category: tuple[str, str, str] = (row["Method"], row["Category"], row["Indicator"])
        
        if row["CF"] is None:
            continue
        
        if impact_category not in lcia_data:
            lcia_data[impact_category]: list = []
            
        ID: (tuple[str, str], None) = mapping.get(drop_unspecified(row["Name"], row["Compartment"], row["Subcompartment"]))
        
        if ID is None:
            raise ValueError("Could not find biosphere flow '{}' in biosphere '{}'".format(drop_unspecified(row["Name"], row["Compartment"], row["Subcompartment"]), biosphere_db_name))
        
        to_append: tuple[tuple[str, str], float] = (ID, float(row["CF"]))
        lcia_data[impact_category] += [to_append]
            
    methods: list = []
    for method_tuple, _ in lcia_data.items():
        methods += [{"name": method_tuple,
                     "unit": units_mapping.get(method_tuple, "Unknown"),
                     "filepath": str(XML_LCIA_filepath),
                     "ecoinvent_version": "ecoinvent version not indicated" if ecoinvent_version is None else ecoinvent_version,
                     "database": biosphere_db_name,
                     "exchanges": lcia_data[method_tuple]
                     }]
    
    return methods

# Copied and adapted from the Brightway ecoinvent 'get_ecoinvent_release' function
def register_XML_LCIA_methods(methods: list) -> None:
    
    # hp.check_function_input_type(register_XML_LCIA_methods, locals())
    for item in methods:
        
        if item["name"] in bw2data.methods:
            del bw2data.methods[item["name"]]
        
        method = bw2data.Method(item["name"])
        method.register(unit = item["unit"],
                        filepath = item["filepath"],
                        ecoinvent_version = item["ecoinvent_version"],
                        database = item["database"]
                        )
        
        method.write(item["exchanges"])
        # print("Registered Brightway method '{}'".format(item["name"]))
    


