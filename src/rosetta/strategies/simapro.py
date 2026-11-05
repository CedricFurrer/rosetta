"""Strategies specific to SimaPro CSV inventory exports."""
import re


from .. import _helpers as hp
from ..defaults.compartments import (
    SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING,
    SIMAPRO_PRODUCT_COMPARTMENTS,
    SIMAPRO_TECHNOSPHERE_COMPARTMENTS,
)

starting: str = "------------"

__all__ = [
    "add_SimaPro_categories_and_category_type",
    "add_SimaPro_classification",
    "add_allocation_field",
    "add_output_amount_field",
    "drop_final_waste_flows",
    "extract_ecoinvent_UUID_from_SimaPro_comment_field",
    "extract_geography_from_SimaPro_name",
    "identify_and_detoxify_SimaPro_name_of_ecoinvent_inventories",
]


def extract_geography_from_SimaPro_name(db_var,
                                        placeholder_for_not_identified_locations: str = "not identified"):
    
    """ Extract the geography from the SimaPro inventory names and write it to a key 'location'.
    The original SimaPro name is set to ``SimaPro_name``."""
    
    # Check function input type
    hp.check_function_input_type(extract_geography_from_SimaPro_name, locals())
    
    # Define the patterns needed
    # Extract everything in between curly brackets
    pat_curly_brackets = "^(?P<name_I>.*\{)(?P<country>[A-Za-z0-9\s\-\&\/\+\,]{2,})(?P<name_II>\}.*)$"
    
    # A general SimaPro pattern. Characters after '/' are identified as locations
    pat_simapro_general = "^(?P<name_I>.*\/)(?P<country>[A-Za-z\-]{2,})(?P<name_II>\s([A-Za-z0-9\s]{2,})?(S|U))$"
    
    # Specific pattern that is used in the SALCA database
    pat_SALCA = "^(?P<name_I>.*\/(?P<unit>[A-Za-z0-9]+)\/)(?P<country>[A-Z]{2,})(?P<name_II>(\/I)?\s(.*)(S|U|$))"
    
    # Set up the function to extract the patterns from the inventory names
    def apply_regex(name_string, pat1, pat2, pat3):
        
        # Apply the patterns to the function input variable 'name_string'
        pat1 = re.match(pat_curly_brackets, name_string)
        pat2 = re.match(pat_simapro_general, name_string)
        pat3 = re.match(pat_SALCA, name_string)
        
        # Check if the patterns are found (if None is returned, no pattern is found)
        if pat1 is not None:
            x = pat1
        elif pat2 is not None:
            x = pat2
        elif pat3 is not None:
            x = pat3
        else:
            # If no pattern has been found, simply return None
            return None
        
        # Otherwise return the grouped dictionary
        return x.groupdict()
    
    # Loop through each inventory in the database
    for ds in db_var:
        
        # Apply the function to extract the location and the new inventory name
        extracted_from_ds = apply_regex(name_string = ds["name"],
                                        pat1 = pat_curly_brackets,
                                        pat2 = pat_simapro_general,
                                        pat3 = pat_SALCA)
        
        # Check if location has already been extracted and a new location was found
        if "location" not in ds and extracted_from_ds is not None:
                
                # Write the old inventory name to 'SimaPro_name'
                ds["SimaPro_name"] = str(ds["name"])
            
                # Extract the new inventory name and overwrite the existing key 'name'
                ds["name"] = str(extracted_from_ds["name_I"]) + "{COUNTRY}" + str(extracted_from_ds["name_II"])
            
                # Add the location
                ds["location"] = str(extracted_from_ds["country"])
        
        # Check if location has already been tried to extract and was not sucessfully found. In that case, we do it again and try again to extract something.
        elif ds.get("location", "") == placeholder_for_not_identified_locations and extracted_from_ds is not None:
                
            # Check if the new country is again COUNTRY. If yes, we don't want to add it.
            if not bool(re.search("COUNTRY", extracted_from_ds["country"])):
                
                # Write the old inventory name to 'SimaPro_name'
                ds["SimaPro_name"] = str(ds["name"])
            
                # Extract the new inventory name and overwrite the existing key 'name'
                ds["name"] = str(extracted_from_ds["name_I"]) + "{COUNTRY}" + str(extracted_from_ds["name_II"])
            
                # Add the location
                ds["location"] = str(extracted_from_ds["country"])
           
        elif "location" in ds:
            "nothing to do"
            
        else:
            # Write the old inventory name to 'SimaPro_name'
            ds["SimaPro_name"] = str(ds["name"])
                
            # Add 'not identified' for the location
            ds["location"] = placeholder_for_not_identified_locations
        
        
        
        # Loop through each exchange in the inventory 'ds'
        for exc in ds.get("exchanges", []):
            
            # Only go on with extracting the location if the exchange is not of type 'biosphere'
            if exc["type"] == "biosphere":
                continue
            
            else:
                
                # Again apply the function to extract the location and the new name of the current exchange
                extracted_from_exc = apply_regex(name_string = exc["name"],
                                                 pat1 = pat_curly_brackets,
                                                 pat2 = pat_simapro_general,
                                                 pat3 = pat_SALCA)
                
                # Check if location has already been extracted
                if "location" not in exc and extracted_from_exc is not None:
                    
                    # Write the old exchange name to 'SimaPro_name'
                    exc["SimaPro_name"] = str(exc["name"])
                
                    # Extract the new exchange name and overwrite the existing key 'name'
                    exc["name"] = str(extracted_from_exc["name_I"]) + "{COUNTRY}" + str(extracted_from_exc["name_II"])
            
                    # Add the location
                    exc["location"] = str(extracted_from_exc["country"])
                
                
                # Check if location has already been tried to extract and was not sucessfully found. In that case, we do it again and try again to extract something.
                elif exc.get("location", "") == placeholder_for_not_identified_locations and extracted_from_exc is not None:
                    
                    # Check if the new country is again COUNTRY. If yes, we don't want to add it.
                    if not bool(re.search("COUNTRY", extracted_from_exc["country"])):
                    
                        # Write the old exchange name to 'SimaPro_name'
                        exc["SimaPro_name"] = str(exc["name"])
                    
                        # Extract the new exchange name and overwrite the existing key 'name'
                        exc["name"] = str(extracted_from_exc["name_I"]) + "{COUNTRY}" + str(extracted_from_exc["name_II"])
                
                        # Add the location
                        exc["location"] = str(extracted_from_exc["country"])
                
                elif "location" in exc:
                    "nothing to do"
                    
                else:
                    # Write the old exchange name to 'orig_name'
                    exc["SimaPro_name"] = str(exc["name"])
                    
                    # Add 'not identified' for the location
                    exc["location"] = placeholder_for_not_identified_locations
            
    return db_var


# Created by Chris Mutel
def drop_final_waste_flows(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through each exchange and only keep the exchange if it is not of type 'Final waste flows'
        # Otherwise, exclude the exchange
        ds["exchanges"] = [exc for exc in ds["exchanges"] if (exc.get("input") or exc["categories"] != ("Final waste flows",))]
    
    return db_var


def add_SimaPro_classification(db_var):
    
    # Initialize list to gather the inventory names where classification was not available
    inventory_classification_not_available: list = []
    
    # Loop through each inventory
    for ds in db_var:
        
        # Go on if all fields are already available
        if "SimaPro_classification" in ds and "SimaPro_categories" in ds and "categories" in ds:
            continue
        
        # Initialize list
        inventory_classification: list = []
        
        # Loop through each exchange
        for exc in ds["exchanges"]:
            
            if exc["type"] == "production":
                
                # The inventory classification is extracted from 'categories' parameter from the production exchange
                inventory_classification += [exc["categories"]]
                
                # Adapt the production exchange
                exc["SimaPro_classification"] = exc["categories"]
                exc["SimaPro_categories"] = (SIMAPRO_PRODUCT_COMPARTMENTS["products"],)
                exc["categories"] = exc["SimaPro_categories"]
                            
        # Raise error if more than one or no production exchange was found
        assert len(inventory_classification) == 1, str(len(inventory_classification)) + " production exchange(s) found. Only one allowed. Check the following inventory:\n\n" + str(ds["name"])

        # If an inventory classification was found, add to the inventory
        if inventory_classification != [] and "SimaPro_classification" not in ds.keys() and not all([x is None for x in inventory_classification]):
            ds["SimaPro_classification"] = inventory_classification[0]
        
        else:
            # Otherwise, add a None
            ds["SimaPro_classification"] = None
            
            # Add to list of errors
            inventory_classification_not_available += [ds["name"]]
    
    # Raise error if inventory classification could not be specified for some inventories
    if inventory_classification_not_available != []:
        raise ValueError("For some inventories, the inventory classification of the output could not be extracted. Error occured in the following inventories:\n\n - " + "\n - ".join(set(inventory_classification_not_available)))
    
    
    return db_var


def add_SimaPro_categories_and_category_type(db_var):

    # Loop through each inventory
    for ds in db_var:
        
        # Go on if all fields are already available
        if "SimaPro_category_type" in ds and "SimaPro_categories" in ds and "categories" in ds:
            continue
        
        # Extract the category type from the SimaPro meta data
        category_type: (str | None) = ds.get("simapro metadata", {}).get("Category type")
        
        # If it is None (not available), add to list
        if category_type is None:
            category_type: str = "material" # We specify here that category type is 'material' if none is provided
        
        # Otherwise, add respective fields
        ds["SimaPro_category_type"]: str = category_type
        ds["categories"]: tuple = (SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING[category_type],)
        ds["SimaPro_categories"]: tuple = (SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING[category_type],)
    
    return db_var


def add_allocation_field(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        # Initialize a list to store all allocation factors
        allocations: list = []
        
        # Loop through each exchange
        for exc in ds["exchanges"]:
            
            # Check if current exchange is of type production
            if exc["type"] == "production":
                
                # For waste treatments, unfortunately no allocation is specified
                # We assume that there is always only one product and therefore the allocation is 100%.
                if ds["SimaPro_categories"] == (SIMAPRO_TECHNOSPHERE_COMPARTMENTS["waste_to_treatment"],):
                    exc["allocation"]: float = float(100)
                
                # Extract allocation
                allocation: (float | None) = exc.get("allocation")
                
                # Raise error if not found
                if allocation is None:
                    raise ValueError("Allocation field not found in production exchange.")
                
                # The inventory classification is extracted from 'categories' parameter from the production exchange
                allocations += [exc["allocation"]]
        
        # Raise error if more than one or no production exchange was found
        assert len(allocations) == 1, str(len(allocations)) + " production exchange(s) found. Only one allowed. Check the following inventory:\n\n" + str(ds["name"])
        
        # Add allocation field to inventory
        ds["allocation"] = float(allocations[0] / 100)
        
    return db_var


def add_output_amount_field(db_var):
    
    # Loop through each inventory
    for ds in db_var:
        
        allocation: (float | None) = ds.get("allocation")
        prod_amount: (float | None) = ds.get("production amount")
        
        if allocation is None:
            raise ValueError("Field 'allocation' not provided in current inventory dictionary.")
        
        if prod_amount is None:
            raise ValueError("Field 'production amount' not provided in current inventory dictionary.")
        
        # Add output amount field to inventory
        ds["output amount"]: float = float(prod_amount * allocation)
        
    return db_var


# A function to extract the ecoinvent activity and product UUID's from the comment fields of SimaPro inventories
def extract_ecoinvent_UUID_from_SimaPro_comment_field(db_var):
    
    # Initialize mapping dictionary to store found activity and reference product codes to after that add to exchanges
    mapping: dict = {}
    
    # Loop through each inventory
    for ds in db_var:
        
        # Extract the comment field of the current inventory
        comment_field: (str | None) = ds.get("simapro metadata", {}).get("Comment")
        
        # If there is no comment field available, we add None's for activity code and reference product code and go to the next inventory because we can not do anyting
        if comment_field is None:
            ds["activity_code"]: None = None
            ds["reference_product_code"]: None = None
            continue
        
        # We construct a specific pattern that matches the logic of how activity and product UUID is stored in the comment field of a SimaPro ecoinvent inventory
        pattern: str = ("^(.*)"
                        "(ource\:)"
                        "( )?"
                        "(.*\_)?"
                        "(?P<activity_code>[A-Za-z0-9\-]{36})"
                        "(\_)"
                        "(?P<reference_product_code>[A-Za-z0-9\-]{36})"
                        "(\.spold)"
                        "(.*)?$")
        
        # Apply the pattern using regex
        extracted = re.match(pattern, comment_field)
        
        # If the pattern does not match, we go to the next item
        if extracted is None:
            ds["activity_code"]: None = None
            ds["reference_product_code"]: None = None
            continue
        
        # Otherwise, we add the found data
        ds["activity_code"]: str = extracted["activity_code"]
        ds["reference_product_code"]: str = extracted["reference_product_code"]
        
        # Add to the mapping dictionary
        mapping[(ds["name"], ds["unit"], ds["location"])]: dict = {"activity_code": extracted["activity_code"],
                                                                   "reference_product_code": extracted["reference_product_code"]}
        
    # Loop through each exchange
    for ds in db_var:
        for exc in ds["exchanges"]:
            
            # Go on if the exchange is of type biosphere
            if exc["type"] == "biosphere":
                continue
            
            # Try to find the activity and reference product code dictionary
            found: (dict | None) = mapping.get((exc["name"], exc["unit"], exc["location"]))
            
            # If found, add to exchange
            if found is not None:
                exc |= found
        
    return db_var


# Break SimaPro names of ecoinvent inventories into the respective fragments of informations
def identify_and_detoxify_SimaPro_name_of_ecoinvent_inventories(db_var,
                                                                cut_patterns: tuple = (" - copied", " - copies")):
    
    # Regex pattern to detoxify the SimaPro names
    # ecoinvent specific!
    pattern_to_detoxify_ecoinvent_name_used_in_SimaPro = ("^"
                                                          "(?P<reference_product>.*[^{}])"
                                                          "(\{)?"
                                                          "(\{)"
                                                          "(?P<location>.*[^{}])"
                                                          "(\})"
                                                          "(\})?"
                                                          "\|"
                                                          "(?P<activity>.*)"
                                                          "\|"
                                                          "( )?"
                                                          "(?P<system_model>[A-Za-z\-]+)"
                                                          "(\, | |\,)??"
                                                          "(?P<process_type>(u|U|s|S))??"
                                                          "$")
    
    # Loop through each inventory and apply the pattern to the inventory name
    for ds in db_var:
        
        # Identify if one of the patterns specified appears in the SimaPro name
        # If yes, then we save the location of the character where the pattern starts
        ds_found: list[int] = [re.search(n.lower(), ds["name"].lower()).start() for n in cut_patterns if n.lower() in ds["name"].lower()]

        # If we found the pattern, we now remove it
        if ds_found != []:
            
            # We split the SimaPro name at the lowest character location
            ds_ending: int = min(ds_found)
            
            # Use slicing to modify name
            # ds["new_name"] = ds["old_name"][:ending]
            ds["name"] = ds["name"][:ds_ending]
        
        # Match pattern
        ds_detoxified_name: (dict | None) = re.match(pattern_to_detoxify_ecoinvent_name_used_in_SimaPro , ds["name"])
        
        # Add key/value pairs to activity
        ds["reference_product_name"]: (str | None) = ds_detoxified_name.groupdict()["reference_product"].strip() if ds_detoxified_name is not None else None
        ds["activity_name"]: (str | None) = ds_detoxified_name.groupdict()["activity"].strip() if ds_detoxified_name is not None else None
        
        # We assume that when the regex pattern matches with the SimaPro name, that the inventory is from the ecoinvent database
        ds["is_ecoinvent"] = ds_detoxified_name is not None
        
        # Loop through each inventory and apply the pattern to the inventory name
        for exc in ds["exchanges"]:
            
            # For biosphere exchanges, we don't need to do it and can go on
            if exc["type"] == "biosphere":
                continue
            
            # Identify if one of the patterns specified appears in the SimaPro name
            # If yes, then we save the location of the character where the pattern starts
            exc_found: list[int] = [re.search(n.lower(), exc["name"].lower()).start() for n in cut_patterns if n.lower() in exc["name"].lower()]
            
            # If we found the pattern, we now remove it
            if exc_found != []:
                
                # We split the SimaPro name at the lowest character location
                exc_ending: int = min(exc_found)
                
                # Use slicing to modify name
                exc["name"] = exc["name"][:exc_ending]
            
            # Match pattern
            exc_detoxified_name: (dict | None) = re.match(pattern_to_detoxify_ecoinvent_name_used_in_SimaPro , exc["name"])
            
            # Add key/value pairs to activity
            exc["reference_product_name"]: (str | None) = exc_detoxified_name.groupdict()["reference_product"].strip() if exc_detoxified_name is not None else None
            exc["activity_name"]: (str | None) = exc_detoxified_name.groupdict()["activity"].strip() if exc_detoxified_name is not None else None
            
            # We assume that when the regex pattern matches with the SimaPro name, that the inventory is from the ecoinvent database
            exc["is_ecoinvent"] = exc_detoxified_name is not None
            
    
    return db_var
