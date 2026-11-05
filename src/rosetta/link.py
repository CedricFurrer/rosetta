import pathlib

import bw2io
import bw2data
from . import helper as hp

#%%
# We have to modify the ExchangeLinker function
# We need to first copy the Linker function from bw2io. Then, we need to adapt the default fields of the 'parse_field' function within the Linker function
# Why do we need to do that? Well, Brightway currently (!! it might change in the future) sets default parameters.
# That means, when linking fields are per default first written to lowercase and stripped and special characters are removed
# HOWEVER, we want to control that by using our parameters
# In order to work properly, we therefore use our values in the 'parse_field' function and set those as a default.

#%% Linking strategies

# Remove the input and output fields (which specify the linking) of certain exchanges
def remove_linking(db_var,
                   production_exchanges: bool = True,
                   substitution_exchanges: bool = True,
                   technosphere_exchanges: bool = True,
                   biosphere_exchanges: bool = True):
    
    # Loop through each inventory
    for ds in db_var:
        
        # Loop through all exchanges and delete the 'input' and 'output' fields
        for exc in ds["exchanges"]:
            
            # Delete linking if the current exchange is of type 'production'
            if production_exchanges and exc["type"] == "production":
                
                # Delete input field
                try: del exc["input"]
                except: pass
                
                # Delete output field
                try: del exc["output"]
                except: pass
            
            # Delete linking if the current exchange is of type 'substitution'
            elif substitution_exchanges and exc["type"] == "substitution":
                
                # Delete input field
                try: del exc["input"]
                except: pass
                
                # Delete output field
                try: del exc["output"]
                except: pass
            
            # Delete linking if the current exchange is of type 'technosphere'
            elif technosphere_exchanges and exc["type"] == "technosphere":
                
                # Delete input field
                try: del exc["input"]
                except: pass
                
                # Delete output field
                try: del exc["output"]
                except: pass
            
            # Delete linking if the current exchange is of type 'biosphere'
            elif biosphere_exchanges and exc["type"] == "biosphere":
                
                # Delete input field
                try: del exc["input"]
                except: pass
                
                # Delete output field
                try: del exc["output"]
                except: pass
            
    return db_var


# Internally means, inventories and flows are only linked with data within the same database
def link_activities_internally(db_var,
                               production_exchanges: bool,
                               substitution_exchanges: bool,
                               technosphere_exchanges: bool,
                               relink: bool,
                               case_insensitive: bool,
                               strip: bool,
                               remove_special_characters: bool,
                               verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(link_activities_internally, locals())
    
    # Initialize variable to store the type of exchanges to which linking should be applied
    kinds = ()
    
    # Link production exchanges, yes or no?
    if production_exchanges:
        kinds += ("production",)
    
    # Link production exchanges, yes or no?
    if substitution_exchanges:
        kinds += ("substitution",)
        
    # Link technosphere exchanges, yes or no?
    if technosphere_exchanges:
        kinds += ("technosphere",)
    
    # Retrieve the original function and set it as a custom variable that we can use in this script 
    custom_ExchangeLinker = bw2io.utils.ExchangeLinker
    
    # Adapt default fields
    custom_ExchangeLinker.parse_field.__defaults__ = (case_insensitive, strip, None if not remove_special_characters else custom_ExchangeLinker.re_sub)

    # Apply linking strategy - link only internally
    db_var = custom_ExchangeLinker.link_iterable_by_fields(db_var,
                                                           fields = ("name", "unit", "location"),
                                                           internal = True,
                                                           kind = kinds,
                                                           relink = relink,
                                                           )
    
    return db_var



# Externally means, inventories and flows are linked with data from other already registered databases
def link_biosphere_flows_externally(db_var,
                                    biosphere_db_name: str,
                                    biosphere_db_name_unlinked: (str | None),
                                    other_biosphere_databases: (tuple | None),
                                    linking_order: (tuple | None),
                                    relink: bool,
                                    case_insensitive: bool,
                                    strip: bool,
                                    remove_special_characters: bool,
                                    verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(link_biosphere_flows_externally, locals())
    
    # If biosphere flows should be relinked, remove all linking first
    if relink:
        
        # Loop through each inventory
        for ds in db_var:
            
            # Loop through each exchange
            for exc in ds["exchanges"]:
                
                # Check if the current exchange is of type 'biosphere'
                if exc["type"] == "biosphere":
                    
                    # And remove the linking field (= input)
                    try: del exc["input"]
                    except: pass
    
    # Database names that should be used for linking, based on predefined ordering
    database_list: tuple = (biosphere_db_name, biosphere_db_name_unlinked) if linking_order is None else linking_order
    
    # If relink is True, we need to reverse the order. In that case, we need to first link the database with lowest priority. Otherwise, we possibly might overwrite linked flows from the highest priority database with flows from lower priority databases.
    if relink:
        database_list: tuple = tuple(reversed(database_list))
    
    # Retrieve the original function and set it as a custom variable that we can use in this script 
    custom_ExchangeLinker = bw2io.utils.ExchangeLinker
    
    # Adapt default fields
    custom_ExchangeLinker.parse_field.__defaults__ = (case_insensitive, strip, None if not remove_special_characters else custom_ExchangeLinker.re_sub)
    
    # Loop through each database name individually and link the data
    for name in database_list:
        
        # ... 1) we link both, top and subcategory
        db_var = bw2io.utils.ExchangeLinker.link_iterable_by_fields(db_var,
                                                                    other = (m for m in bw2data.Database(name)),
                                                                    fields = ("name", "top_category", "sub_category", "location", "unit"),
                                                                    internal = False,
                                                                    kind = {"biosphere"},
                                                                    relink = relink
                                                                    )
        
        # ... 2) we only match the top category without relinking the already linked flows
        db_var = bw2io.utils.ExchangeLinker.link_iterable_by_fields(db_var,
                                                                    other = (m for m in bw2data.Database(name) if len(m["categories"]) == 1),
                                                                    fields = ("name", "top_category", "location", "unit"),
                                                                    internal = False,
                                                                    kind = {"biosphere"},
                                                                    relink = relink
                                                                    )
        
    return db_var



# Externally means, inventories and flows are linked with data from other already registered databases
# In case of duplicates across background databases within the componenet of the linked_fields, 
# the order in which you link the db_var to the background database (parameter link_to_datbases) decides which exchange is linked to the product
# Therefore, modifying the linked fields to add "database" for example can allow the person to link to the correct exchange 
def link_activities_externally(db_var,
                               link_to_databases: tuple,
                               link_production_exchanges: bool,
                               link_substitution_exchanges: bool,
                               link_technosphere_exchanges: bool,
                               relink: bool,
                               case_insensitive: bool,
                               strip: bool,
                               remove_special_characters: bool,
                               linked_fields: tuple = ("name", "unit", "location"),
                               verbose: bool = True):
    
    # Make variable check
    hp.check_function_input_type(link_activities_externally, locals())
    
    # Initialize variable to specify which types of exchanges to link
    kinds = ()
    
    # If specified, exchanges of type 'production' will be linked
    if link_production_exchanges:
        kinds += ("production",)
    
    # If specified, exchanges of type 'substitution' will be linked
    if link_substitution_exchanges:
        kinds += ("substitution",)
    
    # If specified, exchanges of type 'technosphere' will be linked
    if link_technosphere_exchanges:
        kinds += ("technosphere",)
    
    # If no kinds have been specified, we can not link and therefore return the database without having applied any linking
    if kinds == ():
        return db_var

    if relink:
        
        # If we want to relink, we first start to link with the database of last order
        database_list = tuple(reversed(link_to_databases))
    
    else:
        # Otherwise, we start with the ordered ones first and then use the unordered ones
        database_list = tuple(link_to_databases)
    
    # Retrieve the original function and set it as a custom variable that we can use in this script 
    custom_ExchangeLinker = bw2io.utils.ExchangeLinker
    
    # Adapt default fields
    custom_ExchangeLinker.parse_field.__defaults__ = (case_insensitive, strip, None if not remove_special_characters else custom_ExchangeLinker.re_sub)
    
    # Loop through each database name and link the data of 'db' to it
    for db_name in database_list:
        
        # Use Brightway specific linking function to do the linking
        db_var = bw2io.utils.ExchangeLinker.link_iterable_by_fields(db_var,
                                                                    other = (m for m in bw2data.Database(db_name)),
                                                                    fields = linked_fields,
                                                                    internal = False,
                                                                    kind = kinds,
                                                                    relink = relink)
        
    return db_var



