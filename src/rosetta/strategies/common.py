"""Strategies shared by LCI and LCIA imports: biosphere flow normalization, codes, selection and renaming.

A strategy takes a list of dataset dicts and returns the (modified) list.
"""
import copy
import datetime
import hashlib
import json
import re

import pandas as pd

from .. import _helpers as hp
from .._paths import CAS_FILE, uuid_registry_file
from ..defaults.categories import (
    SIMAPRO_BIO_SUBCATEGORIES_MAPPING,
    SIMAPRO_BIO_TOPCATEGORIES_MAPPING,
)
from ..defaults.locations import LOCATIONS
from ..defaults.units import (
    backward_unit_normalization_mapping,
    unit_transformation_mapping,
)

starting: str = "------------"

__all__ = [
    "add_code_field",
    "add_location_to_biosphere_exchanges",
    "add_top_and_subcategory_fields_for_biosphere_flows",
    "add_top_category_factors_as_proxy_for_sub_categories",
    "change_database_name",
    "create_SimaPro_fields",
    "ensure_categories_are_tuples",
    "normalize_and_add_CAS_number",
    "normalize_simapro_biosphere_categories",
    "remove_duplicates",
    "remove_exchanges_with_zero_amount",
    "select_inventory_using_regex",
    "set_code",
    "transformation_units",
    "unregionalize_biosphere",
]


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
    with open(CAS_FILE, "r") as file:
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


def select_inventory_using_regex(db_var, exclude: bool, include: bool, patterns: list, case_sensitive: bool = True):
    
    # Check function input type
    hp.check_function_input_type(select_inventory_using_regex, locals())
    
    # Raise error if exlude and include was both specified. This is not possible
    if exclude and include:
        raise ValueError("Parameters 'include' and 'exclude' can not be True at the same time. It is only possible to either exlude or include.")
    
    # If exlude nor include was specified, just return the database in its original state
    if not exclude and not include:
        return db_var
    
    # We also return the database if no patterns were specified, because selecting does not make sense without a pattern
    if patterns == []:
        return db_var
    
    # Merge the different patterns to a string
    pattern_string = "|".join([str(m) for m in patterns]).lower()
    
    # Initialize a new list to store the new inventories to
    new_db_var = []
    
    # Loop through each inventory and select whether to in- or exlude it based on patterns
    for ds in db_var:
        
        # Check if the pattern is contained in the SimaPro name
        contained = bool(re.search(pattern_string, ds["SimaPro_name"].lower()))
        
        # Remove, if specified and the pattern is contained
        if contained and exclude:
            continue
        
        # Otherwise, if the pattern is not contained, we keep the inventory (by adding it to the new list)
        elif not contained and exclude:
            new_db_var += [ds]
            continue
        
        # If the pattern is contained and we want to include the pattern, write the dataset to the new list
        elif contained and include:
            new_db_var += [ds]
            continue
            
    return new_db_var


def set_code(db_var,
             fields: (tuple | list),
             overwrite: bool,
             strip: bool,
             case_insensitive: bool,
             remove_special_characters: bool):

    # Path to input file where UUIDs are stored
    # Defaults to 'UUIDs.xlsx' inside the package; can be overwritten with the environment variable 'ROSETTA_UUID_FILE'
    file_path = uuid_registry_file()
    
    # Current date formatted as a string
    current_date_string = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # We exclude 'NA' because it refers to country abbreviation and should be read as 'NA' string instead of float("NaN")
    na_values = ["", 
                 "#N/A", 
                 "#N/A N/A", 
                 "#NA", 
                 "-1.#IND", 
                 "-1.#QNAN", 
                 "-NaN", 
                 "-nan", 
                 "1.#IND", 
                 "1.#QNAN", 
                 "<NA>", 
                 "N/A", 
                 # "NA", 
                 "NULL", 
                 "NaN", 
                 "n/a", 
                 "nan", 
                 "null"]
    
    # Initialize variable to store all mapping UUIDs
    UUID_mapping: dict = {}
    
    # Create empty excel file if not yet existing
    if not file_path.exists():
        pd.DataFrame(columns = ("UUID",) + tuple(fields) + ("date_created",)).to_excel(file_path, sheet_name = "UUIDs")
    
    # Import existing UUIDs from Excel file
    UUIDs_orig = pd.read_excel(file_path, sheet_name = "UUIDs", na_values = na_values, keep_default_na = False) 
    
    # Check if all fields provided can be found in the Excel file
    not_specified_in_excel = [m for m in fields if m not in UUIDs_orig.columns]
    
    # If not, raise error indicating the fields hwich are not provided
    if not_specified_in_excel != []:
        raise ValueError("The field(s) '" + ", ".join(not_specified_in_excel) + "' is/are not specified as column in the excel file '" + str(file_path) + "'")
    
    # Extract all rows which contain at least one missing value
    rows_with_nan = UUIDs_orig[UUIDs_orig.isnull().any(axis = 1)]
    
    # Raise error if rows are found that do not contain all information according to the fields specified
    if len(rows_with_nan) > 0:
        raise ValueError("Some rows in file 'UUIDs.xlsx' contain missing fields.")
    
    # Loop through each line in the excel file
    for item in UUIDs_orig.to_dict("records"):
        
        # Create the unique key (= ID) by using the parsing function
        key = hp.format_values(tuple([item[m] for m in fields]),
                               case_insensitive = case_insensitive,
                               strip = strip,
                               remove_special_characters = remove_special_characters)
        
        # The value is simply retrieved from the UUID column
        value = item["UUID"]
        
        # We don't add to the mapping file, if the exact same key already exists
        if key in UUID_mapping:
            continue
        
        # Add information to mapping dictionary
        UUID_mapping[key] = value
    
    # Initialize variable to store the amount of missing fields from the activities
    missing_fields = {m: 0 for m in fields}
    missing_fields_error = False
    
    # Initialize a list where newly created UUIDs can be stored, in order to be written to the excel afterwards
    new_UUIDs: list = []
    
    # Loop through all activities
    for ds in db_var:
        
        # If a code field is already existing and we do not want to overwrite the code, go to next activity
        if "code" in ds and not overwrite:
            continue

        # Loop through each relevant field (previously specified)
        for field in fields:
            
            # If field is missing, write to variable -> will raise error in the end
            # Reason: we can only assign an UUID correctly, if all fields specified can be found for all activities
            if ds.get(field) is None:
                missing_fields[field] += 1
                missing_fields_error = True
        
        # Use the format values function to check for the uniqueness of the flow
        ID = hp.format_values(tuple([ds.get(m) for m in fields]),
                              case_insensitive = True,
                              strip = True,
                              remove_special_characters = False)
        
        # Either use existing UUID from Excel file or create a new one
        if ID in UUID_mapping:
            
            # If the ID is already existing in the Excel file (= in mapping), use it
            UUID = UUID_mapping[ID]
            
        else:
            # Otherwise, create a new UUID
            UUID = str(hashlib.md5("".join([m for m in ID if m is not None]).encode("utf-8")).hexdigest())
            
            # Write the new UUID to the list in order to be added to the Excel afterwards
            new_UUIDs += [dict({field: ds.get(field) for field in fields},
                               **{"UUID": UUID, "date_created": current_date_string})]
        
        # Add code field with the UUID found/created
        ds["code"]: str = UUID
        
        # Raise error if None or more than one production exchange was found
        prod_exchanges = [m for m in ds["exchanges"] if m["type"] == "production"]
        assert len(prod_exchanges) == 1, str(len(prod_exchanges)) + " production exchange(s) was/were found. Allowed is only one. Allocate products/inventories first and make sure to only provide one production exchange. Error occured in " + str(ds)
        
        # We also need to adapt the production exchange
        for exc in ds["exchanges"]:
            
            # Only modify if the current exchange is a production exchange
            if exc["type"] == "production":
            
                # Delete output field
                try: del exc["output"]
                except: pass
                
                # Overwrite or create 'code' field with the new code of the inventory
                exc["code"]: str = UUID
                
                # Overwrite or create 'input' field with the new code of the inventory and the database
                exc["input"]: tuple = (ds["database"], UUID)
                

    # Raise error if fields were not found in activities
    if missing_fields_error:
        formatted_error = "The following fields were found to be missing (of a total of " + str(len(db_var)) + " inventories)\n" + "\n".join([" - '" + k + "' --> missing in " + str(v) + " activity/ies" for k, v in missing_fields.items() if v > 0])
        raise ValueError(formatted_error)
    
    # Write dataframe with new UUIDs
    pd.DataFrame(UUIDs_orig.to_dict("records") + new_UUIDs).to_excel(file_path, sheet_name = "UUIDs", index = False)
 
    return db_var


# Erase all exchanges that have a zero amount
def remove_exchanges_with_zero_amount(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through the whole list of exchanges and keep only the ones that are of type production or where amount is greater than 0
        ds["exchanges"]: list[dict] = [exc for exc in ds["exchanges"]
                                       if exc["type"] == "production" or exc["amount"] != 0]
        
    return db_var


def remove_duplicates(db_var,
                      fields: (tuple | list),
                      strip: bool,
                      case_insensitive: bool,
                      remove_special_characters: bool):
    
    # Make variable check
    hp.check_function_input_type(remove_duplicates, locals())
    
    # Initialize a variable to store all elements already found
    container: dict = {}
    
    # Initialize a variable to store the new list without the duplicates
    new_db_var: list = []
    
    # Initialize variable to store the amount of missing fields from the inventories
    missing_fields: dict = {m: 0 for m in fields}
    missing_fields_error: bool = False
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through each relevant field (previously specified)
        for field in fields:
            
            # If field is missing, write to variable -> will raise error in the end
            # Reason: we can only remove duplicates correctly, if all fields specified can be found for all inventories
            if ds.get(field) is None:
                missing_fields[field] += 1
                missing_fields_error: bool = True
        
        # Create the ID of the current inventory to check if it can be a duplicate            
        ID = hp.format_values(tuple([ds[m] for m in fields]),
                              case_insensitive = case_insensitive,
                              strip = strip,
                              remove_special_characters = remove_special_characters)
        
        # Check if ID has already been found (... and was stored in container)
        # If yes, the current ID is a duplicate and we erase it --> we just don't add it to the new list
        if container.get(ID, False):
            continue
        
        # Add the inventory to the new list
        new_db_var += [ds]
        
        # Update the container dictionary, in case we would find the same ID again further in the loop
        container[ID]: bool = True
        
    
    # Raise error if fields were not found in inventories
    if missing_fields_error:
        formatted_error = "The following fields were found to be missing (of a total of " + str(len(db_var)) + " inventories)\n" + "\n".join([" - '" + k + "' --> missing in " + str(v) + " inventory/ies" for k, v in missing_fields.items() if v > 0])
        raise ValueError(formatted_error)
            
    return new_db_var


def unregionalize_biosphere(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through all exchanges
        for exc in ds["exchanges"]:
            
            # Check if current exchange is of type biosphere
            if exc["type"] == "biosphere":
                
                # Unregionalize, overwrite with GLO
                exc["location"]: str = "GLO"
                
    return db_var


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


