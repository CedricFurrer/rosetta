"""Post-processing of registered LCIA methods."""

import copy
import pathlib

import bw2data
import pandas as pd

from . import _helpers as hp

starting: str = "------------"


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
