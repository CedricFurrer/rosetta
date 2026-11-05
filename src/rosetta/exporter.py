import os
import pathlib

import bw2data
import datetime
import numpy as np
from . import helper as hp
from .defaults.compartments import (SIMAPRO_COMPARTMENTS,
                                   SIMAPRO_COMPARTMENT_ORDER)

#%% Local path
here: pathlib.Path = pathlib.Path(__file__).parent

#%% Create reverse SimaPro normalization mappings for units and categories

# Uncertainty SimaPro normalization mapping
uncertainty_normalization_mapping: dict = {0: {"name": "Undefined", "params": []},
                                           1: {"name": "Undefined", "params": []},
                                           2: {"name": "Lognormal", "params": ["scale"]},
                                           3: {"name": "Normal", "params": ["scale"]},
                                           4: {"name": "Uniform", "params": ["minimum", "maximum"]},
                                           5: {"name": "Triangle", "params": ["minimum", "maximum"]}}

#%% Function to create a SimaPro CSV string from a Peewee object

def export_SimaPro_CSV_from_Peewee(Brightway2_Peewee_object: bw2data.backends.peewee.proxies.Activity,
                                   separator: str = "\t"):
    
    # Check function input types
    hp.check_function_input_type(export_SimaPro_CSV_from_Peewee, locals())
    
    # Initialise dictionary to store final information
    compartment_dict = {}
    
    
    
    def add_to_compartment_dict(key: str, value: str):
        
        # Check function input type
        hp.check_function_input_type(add_to_compartment_dict, locals())
        
        # Assign value to final dictionary
        if key not in compartment_dict:
            compartment_dict[key] = value
        else:
            compartment_dict[key] = compartment_dict.copy()[key] + "\n" + value

    
    def extract_uncertainty_fields(exchange: dict):
        
        # Extract uncertainty for better handling 
        uncertainty = exchange["uncertainty type"]
        
        # Recalculate uncertainty parameters to SimaPro standard
        scale = np.exp(2 * float(exc["scale"])) if uncertainty in [2] else (float(exc["scale"]) ** 2 if uncertainty in [3] else None)
        shape = None
        minimum = exc.get("minimum")
        maximum = exc.get("maximum")
        
        # Specify fields
        field_1 = str(scale if scale is not None else (shape if shape is not None else 0))
        field_2 = str(minimum if minimum is not None else 0)
        field_3 = str(maximum if maximum is not None else 0)
        
        return field_1, field_2, field_3
    
    
    
    def make_string(values: list | tuple):
        
        # Check function input type
        hp.check_function_input_type(make_string, locals())
        
        return separator.join([str(m) for m in values])

    
    # Extract inventory and exchanges as dictionaries
    inventory = Brightway2_Peewee_object.as_dict()
    exchanges = [n.as_dict() for n in Brightway2_Peewee_object.exchanges()]
    
    # Initialise variable to check for the amount of production exchanges
    prod_exc_counter = 0
    
    # Loop through each exchange
    for exc in exchanges:
        
        
        
        ##### EXCHANGE VALIDATION #### 
        ##############################
        
        # Create beautiful string of the current exchange dictionary which can be used for error handling
        exc_beautiful = " - " + "\n - ".join([str(k) + " = '" + str(v) + "'" for k, v in exc.items()])
        
        expected_keys = ("type", "SimaPro_name", "SimaPro_categories", "SimaPro_unit", "amount")
        expected_types = (str, str, tuple, str, float | int)
        
        for idx, key in enumerate(expected_keys):
            
            if exc.get(key) is None:
                raise ValueError("Key '" + str(key) + "' not found in exchange\n\n" + exc_beautiful)
            
            if not isinstance(exc[key], expected_types[idx]):
                raise ValueError("Key '" + str(key) + "' has wrong instance type " + str(type(key)) + ". Should be <class '" + str(expected_types[idx]) + "'>.")
        
        if exc["type"] in ["production"]:
            if exc.get("allocation") is None:
                raise ValueError("Key 'allocation' not found in production exchange\n\n" + exc_beautiful)      

        if exc["type"] not in ["production"]:
            
            if exc.get("uncertainty type") is None:
                raise ValueError("Key 'uncertainty type' not found in exchange\n\n" + exc_beautiful)
            
            if exc["uncertainty type"] > 5:
                raise ValueError("Current uncertainty type '" + str(uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]) + "' can not be exported because it is not implemented in SimaPro.")
            
            if uncertainty_normalization_mapping.get(exc["uncertainty type"]) is None:
                raise KeyError("Uncertainty type '" + str(exc["uncertainty type"]) + "' could not be transformed to SimaPro standard because no mapping is defined.")
            
            missing_params = [m for m in uncertainty_normalization_mapping[exc["uncertainty type"]]["params"] if m not in exc]
            if missing_params != []:
                raise ValueError("Parameters/exchange keys " + str(tuple(missing_params)) + " for specifying uncertainty type '" + str(uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]) + "' were not found in exchange\n\n" + exc_beautiful)
            
        # if unit_normalization_mapping.get(exc["unit"]) is None:
        #     raise KeyError("Unit '" + str(exc["unit"]) + "' could not be transformed to SimaPro standard because no mapping is defined.")
        
        ##############################
        ##############################

        # Dictionary to detect to which compartment the current exchange belongs to
        detected = {SIMAPRO_COMPARTMENTS["products"]: True if exc["type"] == "production" else False,
                    SIMAPRO_COMPARTMENTS["avoided_products"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["avoided_products"], ] else False,
                    SIMAPRO_COMPARTMENTS["resources"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["resources"], "Raw"] else False,
                    SIMAPRO_COMPARTMENTS["materials_fuels"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["materials_fuels"], ] else False,
                    SIMAPRO_COMPARTMENTS["electricity_heat"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["electricity_heat"], ] else False,
                    SIMAPRO_COMPARTMENTS["emissions_air"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["emissions_air"], "Air"] else False,
                    SIMAPRO_COMPARTMENTS["emissions_water"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["emissions_water"], "Water"] else False,
                    SIMAPRO_COMPARTMENTS["emissions_soil"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["emissions_soil"], "Soil"] else False,
                    SIMAPRO_COMPARTMENTS["final_waste_flows"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["final_waste_flows"], "Waste"] else False,
                    SIMAPRO_COMPARTMENTS["non_material_emissions"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["non_material_emissions"], ] else False,
                    SIMAPRO_COMPARTMENTS["social_issues"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["social_issues"], ] else False,
                    SIMAPRO_COMPARTMENTS["economic_issues"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["economic_issues"], "Economic"] else False,
                    SIMAPRO_COMPARTMENTS["waste_to_treatment"]: True if exc["SimaPro_categories"][0] in [SIMAPRO_COMPARTMENTS["waste_to_treatment"], ] else False}
        
        # Check which compartment(s) have been identified for the current exchange
        compartments_are_true = [k for k, v in detected.items() if v]
        
        # If more than one compartment has been identified, raise error
        if len(compartments_are_true) > 1:
            raise ValueError("More than one compartment was identified: " + str(compartments_are_true) + "\n\nError occured in the following exchange:\n" + exc_beautiful)
        
        
        
        
        ####### EXTRACT INFO ######### 
        ##############################
        
        # ... Products
        if detected[SIMAPRO_COMPARTMENTS["products"]]:
            
            # # Column description for 'Products'
            # product_cols = ("name", "unit", "amount", "allocation", "waste_category", "project")
                        
            prod_name = exc["SimaPro_name"]
            prod_unit = exc["SimaPro_unit"]
            prod_amount = (exc["amount"] * exc["allocation"]) / 100
            prod_allocation = exc["allocation"]
            prod_waste = "not defined"
            prod_project = "\\".join(exc["SimaPro_classification"]) if exc.get("SimaPro_classification") is not None else "\\?"
            
            # Values for products
            prod_values = (prod_name, prod_unit, prod_amount, prod_allocation, prod_waste, prod_project)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["products"],
                                    make_string(prod_values))
            
            # Check if allocation is 100%. If not, we need to assign an additional dummy product because SimaPro does not accept products where allocation does not add up to 100%
            if prod_allocation < 100:
                
                # Extract how much more allocation is needed
                prod_allocation_add = 100 - prod_allocation
                
                # Give a name to the dummy product, specify the amount and the inventory category
                prod_name_add = "[Allocation Dummy] " + prod_name
                prod_amount_add = 0
                prod_project_add = prod_project + "\\Allocation_Dummies"
                
                # Values of the dummy product
                prod_values_add = (prod_name_add, prod_unit, prod_amount_add, prod_allocation_add, prod_waste, prod_project_add)
                
                # Create string and add to compartment dictionary
                add_to_compartment_dict(SIMAPRO_COMPARTMENTS["products"],
                                        make_string(prod_values_add))
                
            # Raise error if the allocation is more than 100% because that can not be!
            elif prod_allocation > 100:
                raise ValueError("The allocation of the product of the current inventory is more than 100%!?" )
            
            # Raise production exchange counter
            prod_exc_counter += 1
            continue
            
        
        
        
        # ... Avoided products
        if detected[SIMAPRO_COMPARTMENTS["avoided_products"]]:
            
            # # Column description for 'Avoided products'
            # av_cols = ("name", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            av_name = exc["SimaPro_name"]
            av_unit = exc["SimaPro_unit"]
            av_amount = exc["amount"]
            av_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            av_uncertainty_1, av_uncertainty_2, av_uncertainty_3 = extract_uncertainty_fields(exc)
            av_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for avoided products
            avoided_products_values = (av_name, av_unit, av_amount, av_uncertainty, av_uncertainty_1, av_uncertainty_2, av_uncertainty_3, av_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["avoided_products"],
                                    make_string(avoided_products_values))
            continue
        
        
        
        
        # ... Resources
        if detected[SIMAPRO_COMPARTMENTS["resources"]]:
            
            # # Column description for 'Resources'
            # natural_resources_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            na_name = exc["SimaPro_name"]
            na_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            na_sub_category = na_sub_category_orig if na_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            na_unit = exc["SimaPro_unit"]
            na_amount = exc["amount"]
            na_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            na_uncertainty_1, na_uncertainty_2, na_uncertainty_3 = extract_uncertainty_fields(exc)
            na_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for natural resources
            natural_resources_values = (na_name, na_sub_category, na_unit, na_amount, na_uncertainty, na_uncertainty_1, na_uncertainty_2, na_uncertainty_3, na_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["resources"],
                                    make_string(natural_resources_values))
            continue

        
        
        
        # ... Materials/fuels
        if detected[SIMAPRO_COMPARTMENTS["materials_fuels"]]:
            
            # # Column description for 'Materials/fuels'
            # mat_cols = ("name", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            ma_name = exc["SimaPro_name"]
            ma_unit = exc["SimaPro_unit"]
            ma_amount = exc["amount"]
            ma_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            ma_uncertainty_1, ma_uncertainty_2, ma_uncertainty_3 = extract_uncertainty_fields(exc)
            ma_comment = exc["comment"] if exc.get("comment") is not None else ""

            # Values for materials and fuels
            materials_values = (ma_name, ma_unit, ma_amount, ma_uncertainty, ma_uncertainty_1, ma_uncertainty_2, ma_uncertainty_3, ma_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["materials_fuels"],
                                    make_string(materials_values))
            continue

        

        
        # ... Electricity/heat
        if detected[SIMAPRO_COMPARTMENTS["electricity_heat"]]:
            
            # # Column description for 'Electricity/heat'
            # ele_cols = ("name", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            ele_name = exc["SimaPro_name"]
            ele_unit = exc["SimaPro_unit"]
            ele_amount = exc["amount"]
            ele_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            ele_uncertainty_1, ele_uncertainty_2, ele_uncertainty_3 = extract_uncertainty_fields(exc)
            ele_comment = exc["comment"] if exc.get("comment") is not None else ""

            # Values for electricity and heat
            electricity_heat_values = (ele_name, ele_unit, ele_amount, ele_uncertainty, ele_uncertainty_1, ele_uncertainty_2, ele_uncertainty_3, ele_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["electricity_heat"],
                                    make_string(electricity_heat_values))
            continue
        
        
        
        
        # ... Emissions to air
        if detected[SIMAPRO_COMPARTMENTS["emissions_air"]]:
            
            # # Column description for 'Emissions to air'
            # air_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            air_name = exc["SimaPro_name"]
            air_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            air_sub_category = air_sub_category_orig if air_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            air_unit = exc["SimaPro_unit"]
            air_amount = exc["amount"]
            air_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            air_uncertainty_1, air_uncertainty_2, air_uncertainty_3 = extract_uncertainty_fields(exc)
            air_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for emissions to air
            air_values = (air_name, air_sub_category, air_unit, air_amount, air_uncertainty, air_uncertainty_1, air_uncertainty_2, air_uncertainty_3, air_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["emissions_air"],
                                    make_string(air_values))
            continue
        
        
        
        
        # ... Emissions to water
        if detected[SIMAPRO_COMPARTMENTS["emissions_water"]]:
            
            # # Column description for 'Emissions to water'
            # water_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            water_name = exc["SimaPro_name"]
            water_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            water_sub_category = water_sub_category_orig if water_sub_category_orig not in ["(unspecified)", "unspecified"] else ""         
            water_unit = exc["SimaPro_unit"]
            water_amount = exc["amount"]
            water_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            water_uncertainty_1, water_uncertainty_2, water_uncertainty_3 = extract_uncertainty_fields(exc)
            water_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for emissions to water
            water_values = (water_name, water_sub_category, water_unit, water_amount, water_uncertainty, water_uncertainty_1, water_uncertainty_2, water_uncertainty_3, water_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["emissions_water"],
                                    make_string(water_values))
            continue
        
        
        
        # ... Emissions to soil
        if detected[SIMAPRO_COMPARTMENTS["emissions_soil"]]:
            
            # # Column description for 'Emissions to soil'
            # soil_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            soil_name = exc["SimaPro_name"]
            soil_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            soil_sub_category = soil_sub_category_orig if soil_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            soil_unit = exc["SimaPro_unit"]
            soil_amount = exc["amount"]
            soil_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            soil_uncertainty_1, soil_uncertainty_2, soil_uncertainty_3 = extract_uncertainty_fields(exc)
            soil_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for emissions to soil
            soil_values = (soil_name, soil_sub_category, soil_unit, soil_amount, soil_uncertainty, soil_uncertainty_1, soil_uncertainty_2, soil_uncertainty_3, soil_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["emissions_soil"],
                                    make_string(soil_values))
            continue
        
        
        
        
        # ... Final waste flows
        if detected[SIMAPRO_COMPARTMENTS["final_waste_flows"]]:
            
            # # Column description for 'Final waste flows'
            # waste_flow_cols = ("name", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            waste_flow_name = exc["SimaPro_name"]
            waste_flow_unit = exc["SimaPro_unit"]
            waste_flow_amount = exc["amount"]
            waste_flow_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            waste_flow_uncertainty_1, waste_flow_uncertainty_2, waste_flow_uncertainty_3 = extract_uncertainty_fields(exc)
            waste_flow_comment = exc["comment"] if exc.get("comment") is not None else ""

            # Values for final waste flows
            waste_flow_values = (waste_flow_name, waste_flow_unit, waste_flow_amount, waste_flow_uncertainty, waste_flow_uncertainty_1, waste_flow_uncertainty_2, waste_flow_uncertainty_3, waste_flow_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["final_waste_flows"],
                                    make_string(waste_flow_values))
            continue
        
        
        
        
        # ... Non material emissions
        if detected[SIMAPRO_COMPARTMENTS["non_material_emissions"]]:
            
            # # Column description for 'Non material emissions'
            # non_mat_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            non_mat_name = exc["SimaPro_name"]
            non_mat_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            non_mat_sub_category = non_mat_sub_category_orig if non_mat_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            non_mat_unit = exc["SimaPro_unit"]
            non_mat_amount = exc["amount"]
            non_mat_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            non_mat_uncertainty_1, non_mat_uncertainty_2, non_mat_uncertainty_3 = extract_uncertainty_fields(exc)
            non_mat_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for non material emissions
            non_mat_values = (non_mat_name, non_mat_sub_category, non_mat_unit, non_mat_amount, non_mat_uncertainty, non_mat_uncertainty_1, non_mat_uncertainty_2, non_mat_uncertainty_3, non_mat_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["non_material_emissions"],
                                    make_string(non_mat_values))
            continue
        
        
        
        
        # ... Social issues
        if detected[SIMAPRO_COMPARTMENTS["social_issues"]]:
            
            # # Column description for 'Social issues'
            # social_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            social_name = exc["SimaPro_name"]
            social_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            social_sub_category = social_sub_category_orig if social_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            social_unit = exc["SimaPro_unit"]
            social_amount = exc["amount"]
            social_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            social_uncertainty_1, social_uncertainty_2, social_uncertainty_3 = extract_uncertainty_fields(exc)
            social_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for social issues
            social_values = (social_name, social_sub_category, social_unit, social_amount, social_uncertainty, social_uncertainty_1, social_uncertainty_2, social_uncertainty_3, social_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["social_issues"],
                                    make_string(social_values))
            continue
        
        
        
        
        # ... Economic issues
        if detected[SIMAPRO_COMPARTMENTS["economic_issues"]]:
            
            # # Column description for 'Economic issues'
            # economic_cols = ("name", "sub_category", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            economic_name = exc["SimaPro_name"]
            economic_sub_category_orig = exc["SimaPro_categories"][1] if len(exc["SimaPro_categories"]) == 2 else ""
            economic_sub_category = economic_sub_category_orig if economic_sub_category_orig not in ["(unspecified)", "unspecified"] else ""
            economic_unit = exc["SimaPro_unit"]
            economic_amount = exc["amount"]
            economic_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            economic_uncertainty_1, economic_uncertainty_2, economic_uncertainty_3 = extract_uncertainty_fields(exc)
            economic_comment = exc["comment"] if exc.get("comment") is not None else ""
            
            # Values for economic issues
            economic_values = (economic_name, economic_sub_category, economic_unit, economic_amount, economic_uncertainty, economic_uncertainty_1, economic_uncertainty_2, economic_uncertainty_3, economic_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["economic_issues"],
                                    make_string(economic_values))
            continue
        
        
        
        
        # ... Waste to treatment
        if detected[SIMAPRO_COMPARTMENTS["waste_to_treatment"]]:
            
            # # Column description for 'Waste to treatment'
            # waste_treatment_cols = ("name", "unit", "amount", "uncertainty type", "SD", "min", "max", "comment")
            
            waste_treatment_name = exc["SimaPro_name"]
            waste_treatment_unit = exc["SimaPro_unit"]
            waste_treatment_amount = exc["amount"]
            waste_treatment_uncertainty = uncertainty_normalization_mapping[exc["uncertainty type"]]["name"]
            waste_treatment_uncertainty_1, waste_treatment_uncertainty_2, waste_treatment_uncertainty_3 = extract_uncertainty_fields(exc)
            waste_treatment_comment = exc["comment"] if exc.get("comment") is not None else ""

            # Values for waste to treatment
            waste_treatment_values = (waste_treatment_name, waste_treatment_unit, waste_treatment_amount, waste_treatment_uncertainty, waste_treatment_uncertainty_1, waste_treatment_uncertainty_2, waste_treatment_uncertainty_3, waste_treatment_comment)
            
            # Create string and add to compartment dictionary
            add_to_compartment_dict(SIMAPRO_COMPARTMENTS["waste_to_treatment"],
                                    make_string(waste_treatment_values))
            continue
        
        ##############################
        ##############################
            
            
            
        # If we arrive at this point, that means that the current exchange could not have been exported
        # Therefore, we need to raise an error
        raise ValueError("No mechanisms implemented to export the current exchange of type '" + str(exc["type"]) + "'. Error occured in the following exchange:\n\n" + exc_beautiful)
    
    # Raise error if there was more than one production exchange found in the same Brightway inventory
    assert prod_exc_counter == 1, str("Either no or more than one production exchange was found. Function 'export_SimaPro_CSV' can not export inventories with no or more than 1 production exchange")
    
    # Raise error if no products were detected
    assert compartment_dict.get(SIMAPRO_COMPARTMENTS["products"]) is not None, "No products were detected"
    
    # Combine all compartments to a string block
    compartment_string_block = "\n\n".join([str(m) + "\n" + str(compartment_dict.get(m, "")) for m in SIMAPRO_COMPARTMENT_ORDER])
    
    

    
    
    
    # Inventory variables and names in SimaPro
    process = "Process"
    platform_id = "PlatformId"
    category_type = "Category type"
    process_identifier = "Process identifier"
    type_row = "Type"
    process_name = "Process name"
    status = "Status"
    time_period = "Time period"
    geography = "Geography"
    technology = "Technology"
    representativeness = "Representativeness"
    multiple_output_allocation = "Multiple output allocation"
    substitution_allocation = "Substitution allocation"
    cut_off_rules = "Cut off rules"
    capital_goods = "Capital goods"
    boundary_with_nature = "Boundary with nature"
    infrastructure = "Infrastructure"
    date = "Date"
    record = "Record"
    generator = "Generator"
    external_documents = "External documents"
    literature_references = "Literature references"
    collection_method = "Collection method"
    data_treatment = "Data treatment"
    verification = "Verification"
    comment_row = "Comment"
    allocation_rules = "Allocation rules"
    system_description = "System description"

    # Order of the inventory information in SimaPro
    inventory_order = (process, platform_id, category_type,
                       process_identifier, type_row, process_name,
                       status, time_period, geography, technology, representativeness, multiple_output_allocation,
                       substitution_allocation, cut_off_rules, capital_goods, boundary_with_nature, infrastructure,
                       date, record, generator, external_documents, literature_references, collection_method,
                       data_treatment, verification, comment_row, allocation_rules, system_description)
    
    # Export some relevant parameters to a comment dictionary, which will be used to export to SimaPro CSV comment field
    comment_row_value = {"Brightway project": str(bw2data.projects._project_name),
                         "Brightway database name": str(inventory.get("database", "parameter could not be extracted")),
                         "Brightway inventory code": str(inventory.get("code", "parameter could not be extracted")),
                         "Brightway inventory location": str(inventory.get("location", "parameter could not be extracted")),
                         "exported from Brightway": datetime.datetime.now().strftime("%d.%m.%Y")}
    
    # Extract comment field
    comment_field = inventory.get("comment") + "; " if inventory.get("comment") is not None else "" 
    
    # Inventory information as dictionary
    inventory_dict = {process: "",
                      platform_id: "",
                      category_type: "material",
                      process_identifier: "",
                      type_row: "",
                      process_name: "",
                      status: "",
                      time_period: "Unspecified",
                      geography: "Unspecified",
                      technology: "Unspecified",
                      representativeness: "Unspecified",
                      multiple_output_allocation: "Unspecified",
                      substitution_allocation: "Unspecified",
                      cut_off_rules: "Unspecified",
                      capital_goods: "Unspecified",
                      boundary_with_nature: "Unspecified",
                      infrastructure: "No",
                      date: datetime.datetime.now().strftime("%d.%m.%Y"),
                      record: "",
                      generator: "",
                      external_documents: "",
                      literature_references: "",
                      collection_method: "",
                      data_treatment: "",
                      verification: "",
                      comment_row: comment_field + "; ".join(["'" + k + "' = '" + v + "'" for k, v in comment_row_value.items()]),
                      allocation_rules: "",
                      system_description: ""}
    
    # Combine all inventory information to a string block
    inventory_string_block = "\n\n".join([str(m) + "\n" + str(inventory_dict.get(m, "")) for m in inventory_order])
    
    # End of inventory
    the_end = "End"
    
    # Combine all strings
    final_string = "\n\n".join([inventory_string_block, compartment_string_block, the_end])
    
    return final_string


#%% Function to create a SimaPro CSV file from a list of Peewee objects

def export_SimaPro_CSV(list_of_Brightway2_pewee_objects: list,
                       folder_path_SimaPro_CSV: str | pathlib.Path | None = None,
                       file_name_SimaPro_CSV_without_ending: str | None = None,
                       file_name_print_timestamp: bool = True,
                       separator: str = "\t",
                       avoid_exporting_inventories_twice: bool = True,
                       csv_format_version: str = "7.0.0",
                       decimal_separator: str = ".",
                       date_separator: str = ".",
                       short_date_format: str = "dd.MM.yyyy"):
    
    # Check function input types
    hp.check_function_input_type(export_SimaPro_CSV, locals())
    
    # Create a path if not provided by the function
    # If not provided, the local Brightway2 folder will be used to save results
    if folder_path_SimaPro_CSV is None:
        folder_path_SimaPro_CSV = bw2data.projects.output_dir
    
    # Extract current time
    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Create filename if not provided
    if file_name_SimaPro_CSV_without_ending is None:
        
        # Either use or do not use the timestamp in the filename
        # depending on how specified in the function input
        if file_name_print_timestamp:
            
            # Give file name
            filename = current_time + "_SimaPro_CSV"
            
        else:
            # Give file name
            filename = "SimaPro_CSV"
    
    else:
        # The same as above
        if file_name_print_timestamp:
            
            # Give file name
            filename = current_time + "_" + file_name_SimaPro_CSV_without_ending
            
        else:
            # Give filename
            filename = file_name_SimaPro_CSV_without_ending
    
    
    # Mapping of the delimiter to SimaPro name convention
    SimaPro_delimiter_mapping = {"\t": "Tab",
                                 ";": "Semicolon"}
    
    # Raise error if mapping was unsuccessful
    if SimaPro_delimiter_mapping.get(separator) is None:
        raise ValueError("The separator specified '" + str(separator) + "' could not be mapped to SimaPro name convention. Add to the mapping dictionary.")
    
    # Names of the starting block 
    csv_separator_name = "CSV separator"
    csv_format_version_name = "CSV Format version" 
    decimal_separator_name = "Decimal separator"
    date_separator_name = "Date separator"
    short_date_format_name = "Short date format"
    
    # Starting block dictionary --> information needed for the starting block 
    starting_block = {csv_separator_name: SimaPro_delimiter_mapping[separator],
                      csv_format_version_name: csv_format_version,
                      decimal_separator_name: decimal_separator,
                      date_separator_name: date_separator,
                      short_date_format_name: short_date_format}
    
    # Create the starting block string
    starting_block_string = "\n".join(["{" + str(k) + ": " + str(v) + "}" for k, v in starting_block.items()])
    
    # Initialise a list, to store all inventory strings which will be exported
    inv_strings = []
    
    # Initialize a dictionary to store already exported SimaPro names
    already_exported = {}
    
    # Loop through each Brightway2 inventory
    for obj in list_of_Brightway2_pewee_objects:
        
        # SimaPro does not accept inventories with the exact same name. In case we would export the inventory twice, we exclude it so that it is only exported once.
        if avoid_exporting_inventories_twice and obj["SimaPro_name"] in already_exported:
            
            if already_exported[obj["SimaPro_name"]] != (obj["database"], obj["code"]):
                print(already_exported[obj["SimaPro_name"]])
                print((obj["database"], obj["code"]))
                raise ValueError("The SimaPro name '" + obj["SimaPro_name"] + "' is used in different databases. SimaPro does not allow inventories with the same SimaPro name. Thus, the inventory can not be exported twice although it might be different in inputs, outputs, emissions. Make sure to either provide different inventory names or to export only one of the inventories.")

            
            # # We have a problem and need to raise an error, in case we use the same SimaPro name for different inventories from different databases
            # # For additional evaluation, we check duplicated SimaPro names, if they are coming from the same databases and have the same code
            # # If yes, then it is ok. Otherwise, we have a problem and potentially export two inventories with the same name but different inputs, outputs, emissions. In that case, we raise an error.
            # if (obj["database"], obj["code"]) not in already_exported[obj["SimaPro_name"]]:
            #     raise ValueError("The SimaPro name '" + obj["SimaPro_name"] + "' is used in different databases. SimaPro does not allow inventories with the same SimaPro name. Thus, the inventory can not be exported twice although it might be different in inputs, outputs, emissions. Make sure to either provide different inventory names or to export only one of the inventories.")
            
            continue
        
        # Extract the SimaPro specific string of the current inventory and add to list
        inv_strings += [export_SimaPro_CSV_from_Peewee(obj, separator)]
        
        # If we specified to not export inventories twice, write the current SimaPro name to the dictionary so that it is omitted (and not exported) in case it would appear once more again.
        if avoid_exporting_inventories_twice:
            
            already_exported[obj["SimaPro_name"]] = (obj["database"], obj["code"])
            
            # # We add the database and the code of the inventory to the dictionary together with the SimaPro name
            # if obj["SimaPro_name"] in already_exported:
                
            #     # Add tuple to list if key is already there
            #     already_exported[obj["SimaPro_name"]] += [(obj["database"], obj["code"])]
            
            # else:
            #     # Otherwise initialize a new key with a new list containing the tuple
            #     already_exported[obj["SimaPro_name"]] = [(obj["database"], obj["code"])]
    
    # Combine all the inventory strings to one string
    inv_string = "\n\n".join(inv_strings)
    
    # Add the starting block of the SimaPro CSV file to the inventory string
    final_string = "\n\n".join([starting_block_string, inv_string])
    
    # Write to file
    f = open(os.path.join(str(folder_path_SimaPro_CSV), filename + ".csv"), "x", encoding = "utf-8")
    f.write(final_string)
    f.close()
    
    # Print file path to console
    print(str(os.path.join(str(folder_path_SimaPro_CSV), filename + ".csv")))
    
    return final_string





