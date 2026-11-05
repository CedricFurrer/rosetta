"""Strategies specific to ecoinvent ecospold2 (XML) inventories."""
import re


from .. import _helpers as hp
from ..defaults.categories import (
    BACKWARD_SIMAPRO_BIO_SUBCATEGORIES_MAPPING,
    BACKWARD_SIMAPRO_BIO_TOPCATEGORIES_MAPPING,
)
from ..defaults.compartments import (
    SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING,
)
from ..defaults.model_type import (
    XML_TO_SIMAPRO_MODEL_TYPE_MAPPING,
    XML_TO_SIMAPRO_PROCESS_TYPE_MAPPING,
)
from ..defaults.units import (
    backward_unit_normalization_mapping,
)

starting: str = "------------"

__all__ = [
    "add_GLO_to_biosphere_exchanges",
    "assign_categories_from_XML_to_biosphere_flows",
    "assign_flow_field_as_code",
    "flip_sign_of_waste_flows",
    "modify_fields_to_SimaPro_standard",
]


def assign_flow_field_as_code(db_var):
    
    """ Assign the value of field 'flow' (= UUID) as code for biosphere flows.
    Only valid for XML data from ecoinvent!"""
    
    # Loop through each inventory in the database
    for ds in db_var:
        
        # Loop through each exchange in 'ds'
        for exc in ds["exchanges"]:
            
            # Check if the flow is of type biosphere
            if exc["type"] == "biosphere":
                
                # If yes, add a new field 'code'. Use the value of field 'flow' as new value.
                exc["code"] = exc["flow"]
                
                # Delete the old field 'flow'
                del exc["flow"]
            
    return db_var


# Function to assign the biosphere categories from the XML files to the exchange data during ecospold import
def assign_categories_from_XML_to_biosphere_flows(db_var, biosphere_flows):
    
    # Create a code-categories mapping for each biosphere flow
    categories_mapping = {m["code"]: m["categories"] for m in biosphere_flows}
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through each exchange
        for exc in ds["exchanges"]:
            
            # Check if the current exchange is of type 'biopshere'
            if exc["type"] == "biosphere":
                
                # Assign the categories --> compare the current exchange code with the mapping dictionary and find the respective category match
                exc["categories"] = categories_mapping[exc["code"]]
                
    return db_var


# Very specific function to the XML/ecospold data from ecoinvent
# This function transform inventory and exchange dictionaries, so that we have a (almost) identical structure with dictionaries from SimaPro import
def modify_fields_to_SimaPro_standard(db_var,
                                      model_type: str,
                                      process_type: str):
    
    # Check function input type
    hp.check_function_input_type(modify_fields_to_SimaPro_standard, locals())
    
    if model_type not in XML_TO_SIMAPRO_MODEL_TYPE_MAPPING:
        raise ValueError("Provided model type '' is not valid. Use one of the following model type(s) instead:\n - {}".format("n - ".join(list(XML_TO_SIMAPRO_MODEL_TYPE_MAPPING.keys()))))
    
    if process_type not in XML_TO_SIMAPRO_PROCESS_TYPE_MAPPING:
        raise ValueError("Provided process type '' is not valid. Use one of the following process type(s) instead:\n - {}".format("n - ".join(list(XML_TO_SIMAPRO_PROCESS_TYPE_MAPPING.keys()))))
    
    # Initialize a mapping dictionary
    tech_subs_mapping: dict = {}
    
    # Loop through each inventory in the database
    for ds in db_var:
        
        # Extract original data of certain fields and store them in variables
        name = ds["name"]
        reference_product = ds["reference product"]
        location = ds["location"]
        
        # Write new fields in SimaPro standard
        ds["activity_name"] = name
        ds["reference_product_name"] = reference_product
        ds["name"] = reference_product[0].upper() + reference_product.lower()[1:] + " {{COUNTRY}}| " + name.lower() + " | " + XML_TO_SIMAPRO_MODEL_TYPE_MAPPING[model_type] + ", " + XML_TO_SIMAPRO_PROCESS_TYPE_MAPPING[process_type]
        ds["SimaPro_name"] = reference_product[0].upper() + reference_product.lower()[1:] + " {" + location + "}| " + name.lower() + " | " + XML_TO_SIMAPRO_MODEL_TYPE_MAPPING[model_type] + ", " + XML_TO_SIMAPRO_PROCESS_TYPE_MAPPING[process_type]
        ds["categories"]= SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING["material"]
        ds["SimaPro_categories"] = SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING["material"]
        ds["SimaPro_category_type"] = "material"
        ds["synonyms"] = tuple(ds["synonyms"])
        ds["allocation"] = ds.get("properties", {}).get("allocation factor", {}).get("amount", 1)
        ds["output amount"] = float(ds["production amount"] * ds["allocation"])
        ds["code"] = ds["activity"] + "_" + ds["flow"]
        ds["reference_product_code"] = ds["flow"]
        ds["activity_code"] = ds["activity"]
        
        # We try to backward normalize the ecoinvent unit to SimaPro standard
        try:
            ds["SimaPro_unit"] = backward_unit_normalization_mapping[ds["unit"]]
            
        except:
            # If we fail, we need to raise an error
            raise ValueError("Inventory unit (" + str(ds["unit"]) + ") could not be transformed to 'SimaPro_unit' (backward mapped).")

        
        # Delete unused fields
        del ds["flow"], ds["activity"]
        
        # Convert list of classification systems into dictionary of tuples
        # For ecoinvent data, we currently catch only the CPC and ISIC classification systems
        classification_systems = ["CPC", "ISIC"]
        
        # Search for the classification systems and identify the respective tuple
        classifications = [[(n, m[1:]) for n in classification_systems if re.search(n, m[0])][0] for m in ds.get("classifications", []) if re.search("|".join(classification_systems), m[0])]
        
        # If we could successfully identify the classification systems (list is not empty), we add them
        if classifications != []:
            
            # We construct a dictionary for each classification system, where the first tuple element specifies the classification system
            ds |= {system + "_classification": (system,) + cats for system, cats in classifications}
            
            # We use the first classification system in the list of classification systems found as SimaPro_classification
            ds["SimaPro_classification"] = [("ecoinvent",) + ds.get(m + "_classification")[1:] for m in classification_systems if ds.get(m + "_classification") is not None][0]
            
            # We now delete the old classifications key, because we do not need it anymore
            del ds["classifications"]
        
        else:
            # If no classification systems were found, we add an unclassified tuple
            ds["SimaPro_classification"] = ("ecoinvent", "not classified")
         
        # We now extract all the products of the current activity to a list
        products = [m for m in ds["exchanges"] if m["type"] == "production"]
        
        # We check how many products were found. Important: we can only work with activities that have one production exchange. Otherwise, we need to raise an error
        assert len(products) == 1, str(len(products)) + " production exchange(s) found"
        
        # We can now use the only list element as product
        product = products[0]
        
        # We move the 'properties' field from the production exchange to the inventory 'ds' for better accessibility
        if "properties" in product:
            ds["properties"] = product["properties"]
        
        # We loop through each exchange to transform data
        for exc in ds["exchanges"]:
            
            # Modify the production exchange
            if exc["type"] == "production":
                
                # Similar to the 'properties' field above, we loop through specific fields that we have modified in 'ds' and update the fields in the production exchange.
                fields = ["output amount", "activity_name", "reference_product_name", "activity_code", "reference_product_code", "name", "SimaPro_name", "categories", "SimaPro_categories", "unit", "SimaPro_unit", "location"]
                
                # Modify fields
                for field in fields:
                    exc[field] = ds[field]
                
                # Modify allocation field manually
                exc["allocation"] = ds["allocation"] * 100
                
                # Modify input field manually
                exc["input"] = (ds["database"], ds["code"])

            # Delete fields that we do not use anymore.
            # Deletion applies to all types of exchanges
            fields_to_delete = ["classifications", "properties"]
            
            # Loop through each field and delete, if possible
            for del_field in fields_to_delete:
                
                # Try to delete. If field is not found, pass
                try: del exc[del_field]
                except: pass
            
            # Add certain fields for the biosphere flows
            if exc["type"] == "biosphere":
                
                # Add location, if not existing. Take the GLO as default.
                if "location" not in exc:
                    exc["location"] = "GLO"
                
                # Create the SimaPro name from the original name together with the location, separated by a comma (this is the SimaPro standard)
                if "SimaPro_name" not in exc:    
                    exc["SimaPro_name"] = exc["name"] + (", " + exc["location"] if exc["location"] != "GLO" else "")
                
                # Backward map the unit to the SimaPro standard
                if "SimaPro_unit" not in exc:
                    exc["SimaPro_unit"] = backward_unit_normalization_mapping.get(exc["unit"], exc["unit"])
                
                # Backward map the categories to the SimaPro standard
                if "SimaPro_categories" not in exc:
                    
                    # Extract the current categories
                    categories = exc.get("categories")
                    
                    # Extract the top and sub categories and write to individual variables for mapping afterwards
                    top_cat_orig = categories[0].lower() if categories is not None and len(categories) > 0 else ""
                    sub_cat_orig = categories[1].lower() if categories is not None and len(categories) > 1 else ""
                    
                    # Try to map the top and sub categories 'back' to SimaPro standard using the mapping from Brightway
                    top_cat = BACKWARD_SIMAPRO_BIO_TOPCATEGORIES_MAPPING.get(top_cat_orig, top_cat_orig)
                    sub_cat = BACKWARD_SIMAPRO_BIO_SUBCATEGORIES_MAPPING.get(sub_cat_orig, sub_cat_orig)
                    
                    # If we find the a top category match, we were successful and write it to the biosphere exchange
                    if top_cat != "":
                        exc["SimaPro_categories"] = (top_cat, sub_cat) if sub_cat != "" else (top_cat,)
                        
                    else:
                        # If there is no top category provided and we can not map it, raise error
                        raise ValueError("No top category provided for biosphere flow:\n - 'SimaPro_name' = {}\n - 'unit' = {}\n - 'code' = {}".format(exc["SimaPro_name"], exc["unit"], exc["code"]))

                    
                # Add an empty field for the CAS number, if the field is not yet existing
                if "CAS number" not in exc:
                    exc["CAS number"] = ""
            
            # If the current exchange is of one type, that we don't know yet, let's raise an error to inform us
            # Why do we do that? Because we might need to adjust our scripts!
            known_exchange_types = ["production", "biosphere", "substitution", "technosphere"] 
            assert exc["type"] in known_exchange_types, "Exchange type '" + str(exc["type"]) + "' not known. Consider checking and modifying the strategy 'modify_fields_to_SimaPro_standard'."
        
        # Add current inventory to mapping
        tech_subs_mapping[ds["code"]] = ds
    
    # Specify the fields that we need to add or adapt in technosphere and substitution exchanges
    fields_to_adapt_or_add_in_technosphere_and_substitution_exchanges = ["activity_name",
                                                                         "reference_product_name",
                                                                         "activity_code",
                                                                         "reference_product_code",
                                                                         "name",
                                                                         "SimaPro_name",
                                                                         "categories",
                                                                         "SimaPro_categories",
                                                                         "unit",
                                                                         "SimaPro_unit",
                                                                         "location"]
    
    # We need to loop again through it to adapt the technosphere and substitution exchanges
    for ds in db_var:
        for exc in ds["exchanges"]:
            
            # Specify the field names that we want to delete because we do not use them anymore.
            fields_to_delete = ["activity", "flow"]
            
            # We delete the activity and flow codes and go on if the current exchange is not of type 'technosphere' or 'substitution'
            if exc["type"] not in ["technosphere", "substitution"]:
                
                # Loop through each field and delete, if possible
                for del_field in fields_to_delete:
                    
                    # Try to delete. If field is not found, pass
                    try: del exc[del_field]
                    except: pass
                
                continue
            
            # We retrieve the inventory that corresponds to the current exchange
            # The inventory stores the new information, that we need to adapt to the fields in the exchange
            map_to = tech_subs_mapping[exc["activity"] + "_" + exc["flow"]]
            
            # We loop through each field specified beforehand that needs an update
            for adapt_field in fields_to_adapt_or_add_in_technosphere_and_substitution_exchanges:
                
                # We retrieve the field value from the inventory
                map_to_value = map_to.get(adapt_field)
                
                # We update the exchange field if the value is not None
                if map_to_value is not None:
                    exc[adapt_field] = map_to_value
                    
            # Loop through each field and delete, if possible
            for del_field in fields_to_delete:
                
                # Try to delete. If field is not found, pass
                try: del exc[del_field]
                except: pass
    
    return db_var


# Waste flows are defined with a negative production amount in XML data
# For SimaPro, waste flows are with a positive sign. We need to flip the signs for waste flows therefore, when importing XML data.
def flip_sign_of_waste_flows(db_var):
    
    # Specify amount and uncertainty fields where signs will be adjusted 
    exc_uncertainty_field_names: list[str] = ["amount", "loc", "scale", "shape", "minimum", "maximum"]
    
    # Extract all inventory codes where production amount is smaller than 0
    # We assume, that those inventories are of type waste
    # ... once with technosphere fields as key
    unique_fields_with_production_amount_smaller_than_0 = {tuple([m[n] for n in ("name", "unit", "location")]): True for m in db_var if m["production amount"] < 0}
    
    # Initialize dictionaries to store all changed inventories and exchanges
    changed_invs: list = []
    changed_excs: list = []
    
    # Loop through each inventory
    # Identify waste flows and flip signs
    for ds in db_var:
        
        # Check if production amount of the inventory is negative
        inv_amount_is_negative: bool = ds["production amount"] < 0
        
        # If the inventory is of type 
        if inv_amount_is_negative:
            
            # Create a dictionary and store the old inventory production amount
            changed_inv: dict = {"production_amount_old": ds["production amount"]}
            
            # Change the sign of the production amount
            ds["production amount"] *= -1
            
            # Make an entry/dictionary for the Excel table afterwards to store all changes made to inventories
            # Add certain fields that will be shown in the table
            changed_inv |= {**{n: ds[n] for n in ("name", "unit", "location")}, **{"production_amount_new": ds["production amount"], "type": ds["type"]}}
            
            # Add changed inventory as dictionary to the list
            changed_invs += [changed_inv]
        
        # Loop through all exchanges
        for exc in ds["exchanges"]:
            
            # Waste flows are only of type technosphere. Substitution flows do not exist in ecoinvent
            # If the current exchange is not of type technosphere or production, go on, because we don't need to adjust anything
            if exc["type"] not in ["technosphere", "production"]:
                continue
            
            # Check if the inventory was identified with a negative production exchange before and therefore is categorized as 'waste'
            exc_is_waste: bool = unique_fields_with_production_amount_smaller_than_0.get(tuple([exc[n] for n in ("name", "unit", "location")]), False)
            
            # Check if the (production) amount of the inventory is negative
            exc_amount_is_negative: bool = exc["amount"] < 0
            
            # If amount is negative and it is an exchange of type 'waste'
            if exc_is_waste and exc_amount_is_negative:
                
                # Create a dictionary and store the old exchange (production) amount
                changed_exc: dict = {"amount_old": exc["amount"]}
                
                # Adjust all integer/float fields (= amount and uncertainty fields) in the exchange dictionary
                for exc_uncertainty_field_name in exc_uncertainty_field_names:
                    
                    # Check if the current field name is contained in the exchange
                    if exc_uncertainty_field_name in exc:
                        
                        # If yes, adjust the value -> flip it
                        exc[exc_uncertainty_field_name] *= -1
                
                # Update the negative field
                if "negative" in exc:
                    exc["negative"]: bool = exc["amount"] < 0
                
                # Make an entry/dictionary for the Excel table afterwards to store all changes made to exchanges
                # Add certain fields that will be shown in the table
                changed_exc |= {**{n: exc[n] for n in ("name", "unit", "location")}, **{"amount_new": exc["amount"], "type": exc["type"]}}
                
                # Add changed exchange as dictionary to the list
                changed_excs += [changed_exc]
        
        
    # # Create pandas Dataframes first
    # df_changed_invs = pd.DataFrame(changed_invs)
    # df_changed_excs = pd.DataFrame(changed_excs)
    
    # # Write Dataframes to Excel files, if the files are not empty
    # if len(df_changed_invs) > 0:
    #     df_changed_invs.to_excel(local_output_path / "XML_inventories_where_signs_flipped.xlsx")
    #     print("\n'XML_inventories_where_signs_flipped.xlsx' saved to:\n" + str(local_output_path))
        
    # if len(df_changed_excs) > 0:
    #     df_changed_excs.to_excel(local_output_path / "XML_exchanges_where_signs_flipped.xlsx")
    #     print("\n'XML_exchanges_where_signs_flipped.xlsx' saved to:\n" + str(local_output_path))
    
    return db_var


# Add 'GLO' as location to all biosphere exchanges
# We need to do that in order to be consistent with SimaPro flows. As a default, ecoinvent only uses 'GLO' flows
def add_GLO_to_biosphere_exchanges(db_var):
    for ds in db_var:
        for exc in ds["exchanges"]:
            if exc["type"] == "biosphere":
                exc["location"] = "GLO"
    return db_var
