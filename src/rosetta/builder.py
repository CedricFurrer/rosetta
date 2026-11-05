import pathlib

import uuid
import copy
import math
import bw2data
from . import helper as hp

from .defaults.compartments import (SIMAPRO_TECHNOSPHERE_COMPARTMENTS,
                                   SIMAPRO_SUBSTITUTION_COMPARTMENTS,
                                   SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING,
                                   SIMAPRO_PRODUCT_COMPARTMENTS
                                   )

from .defaults.units import backward_unit_normalization_mapping

#%% Function 'create_base_inventory'

# Function to be used to create valid Brightway2 inventories
def create_base_inventory(inv_name: str,
                          inv_SimaPro_name: str,
                          inv_cat: (tuple | None),
                          inv_SimaPro_category_type: str,
                          inv_unit: str,
                          inv_SimaPro_unit: (str | None),
                          inv_location: str,
                          inv_SimaPro_classification: tuple,
                          inv_amount: (float | int),
                          inv_database: str,
                          inv_allocation: (float | int) = 1,
                          inv_type: str = "process",
                          inv_code: (str | None) = None,
                          inv_exchanges: list = [],
                          overwrite_existing_key_value_pairs_with_kwargs: bool = False,
                          **kwargs: dict):
    """
    Create a valid inventory dictionary for Brightway2

    Parameters
    ----------
    inv_name : str
        Inventory name.
    
    inv_SimaPro_name : str
        Inventory name in SimaPro standard.
    
    inv_cat : tuple | None
        Inventory category. If None is provided, will use categories extracted from 'inv_SimaPro_category_type'.
    
    inv_SimaPro_category_type : str
        The category type of the inventory in SimaPro standard.
        One of the following strings are accepted: 'material', 'energy', 'waste treatment', 'processing', 'transport', 'use'

    inv_unit : str
        Inventory unit.
    
    inv_SimaPro_unit : str | None
        Exchange unit in SimaPro standard. If it is not provided, it will be tried to backward map the unit using the 'unit' field and the mapping from Brightway.  
    
    inv_location : str
        Inventory location.
    
    inv_SimaPro_classification : tuple
         The inventory classification given in SimaPro.
    
    inv_amount : (float | int)
        Inventory output amount.
        
    inv_database : str
        Inventory database.

    inv_allocation : (float | int), optional
        Allocation of the current inventory. The default is 1.
        
    inv_type : str, optional
        Inventory type. The default is "process".
        
    inv_code : (str | None), optional
        Inventory code. If no code is provided (= None), a UUID will automatically be generated. The default is None.
    
    inv_exchanges : list, optional
        List of exchanges (inputs, outputs, emissions). The default is an empty list ([]).
    
    overwrite_existing_key_value_pairs_with_kwargs : bool, optional
        Defines whether to check if key/value pairs would be overwritten by **kwargs if **kwargs are given as function inputs. The default is False.
    
    **kwargs : dict
        Additional key/value pairs to be passed to the inventory.

    Returns
    -------
    inv : dict
        An inventory dictionary in valid Brightway2 format is returned.

    """
    
    # Function input variable check
    hp.check_function_input_type(create_base_inventory, locals())
    
    # Check if the amount is 0 and raise error if so.
    if inv_amount <= 0:
        raise ValueError("Input variable 'inv_amount' can not be 0 and can not be negative but is currently" + str(inv_amount) + "! Change.")
    
    # Validate allocation, needs to be between 0 and 1
    if inv_allocation > 1 or inv_allocation <= 0:
        raise ValueError("Input variable 'inv_allocation' must be greater than 0 (can not be 0!) and smaller than 1 but is currently '" + str(inv_allocation) + "'. Change.")
    
    # The only acceptable category types
    if inv_SimaPro_category_type not in SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING:
        raise ValueError("Category type provided by 'inv_SimaPro_category_type' is not accepted. It needs to be one of " + str(list(SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING)) + " but it is currently '" + inv_SimaPro_category_type + "'")
    
    # If no inventory code is provided, one is automatically generated
    if inv_code is None:
        inv_code = str(uuid.uuid4())
    
    # Check if SimaPro unit is provided as function input
    if inv_SimaPro_unit is None:
        
        # If not, map the unit given to the SimaPro standard
        inv_SimaPro_unit_mapped = backward_unit_normalization_mapping.get(inv_unit)
        
        # If mapping has failed, raise error
        if inv_SimaPro_unit_mapped is None:
            raise ValueError("'inv_SimaPro_unit' could not be mapped from 'inv_unit' (" + str(inv_unit) + "). Provide 'inv_SimaPro_unit' as function input (not using None).")
    
    # Initialize empty dictionary for the inventory
    inv = {}
    
    # Add information to inventory dictionary
    inv["name"] = inv_name
    inv["SimaPro_name"] = inv_SimaPro_name
    inv["categories"] = inv_cat if inv_cat is not None else (SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING[inv_SimaPro_category_type],)
    inv["SimaPro_categories"] = (SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING[inv_SimaPro_category_type],)
    inv["SimaPro_category_type"] = inv_SimaPro_category_type
    inv["unit"] = inv_unit
    inv["SimaPro_unit"] = inv_SimaPro_unit if inv_SimaPro_unit is not None else inv_SimaPro_unit_mapped 
    inv["location"] = inv_location
    inv["SimaPro_classification"] = inv_SimaPro_classification
    inv["production amount"] = inv_amount / inv_allocation 
    inv["output amount"] = inv_amount
    inv["allocation"] = inv_allocation
    inv["database"] = inv_database
    inv["type"] = inv_type
    inv["code"] = inv_code
    
    # Make a deepcopy of the inventory dictionary
    # Create the production inventory, which will be added to the exchanges
    prod_inv = copy.deepcopy(inv)
    prod_inv["amount"] = inv_amount / inv_allocation # !!! Check
    prod_inv["type"] = "production"
    prod_inv["allocation"] = inv_allocation * 100
    prod_inv["SimaPro_categories"] = (SIMAPRO_PRODUCT_COMPARTMENTS["products"],)
    prod_inv["input"] = (inv["database"], inv["code"])
    
    # Delete irrelevant key/value pairs of the production inventory dict
    del prod_inv["production amount"]
    del prod_inv["SimaPro_category_type"]
    
    # Create inventory exchanges and add the production inventory dictionary
    inv["exchanges"] = [prod_inv] + inv_exchanges
    
    # Add additional items provided by kwargs to the inventory
    for k, v in kwargs.items():
        
        # Evaluate, if existing key/value pair would be overwritten, in case key are named equally
        if not overwrite_existing_key_value_pairs_with_kwargs and k in inv:
            
            # Throw error, if specified to NOT overwrite
            raise ValueError("Key/value pair already exists in inventory. Problematic key: '" + str(k) + "'.\n\nEither set variable 'overwrite_existing_key_value_pairs_with_kwargs' to True or make sure to NOT pass the key/value pair again to the inventory.")
        else:
            # Otherwise, overwrite
            inv[k] = v
    
    return inv

#%% Function 'create_base_exchange'

# Read the docs 'stats_arrays' for uncertainty
# https://stats-arrays.readthedocs.io/en/latest/

uncertainty_type_mapping = {"undefined": 0,
                            "no uncertainty": 1,
                            "lognormal distr.": 2,
                            "normal distr.": 3,
                            "uniform distr.": 4,
                            "triangular distr.": 5,
                            "bernoulli distr.": 6,
                            "discrete uniform": 7,
                            "weibull": 8,
                            "gamma": 9,
                            "beta distr.": 10,
                            "generalized extreme value": 11,
                            "student's T": 12}

required = {"undefined": ["loc"],
            "no uncertainty": ["loc"],
            "lognormal distr.": ["negative", "loc", "scale"],
            "normal distr.": ["negative", "loc", "scale"],
            "uniform distr.": ["negative", "minimum", "maximum"],
            "triangular distr.": ["negative", "minimum", "maximum"],
            "bernoulli distr.": ["loc"],
            "discrete uniform": ["maximum"],
            "weibull": ["scale", "shape"],
            "gamma": ["scale", "shape"],
            "beta distr.": ["loc", "shape"],
            "generalized extreme value": ["loc", "scale", "shape"],
            "student's T": ["shape"]}

# Function to be used to create valid Brightway2 exchanges
def create_base_exchange(exc_name: str,
                         exc_SimaPro_name: str,
                         exc_cat: tuple,
                         exc_SimaPro_cat: tuple,
                         exc_unit: str,
                         exc_SimaPro_unit: (str | None),
                         exc_location: str,
                         exc_amount: (float | int),
                         exc_type: str,
                         exc_database: (str | None) = None,
                         exc_code: (str | None) = None,
                         exc_uncertainty_type: (str | int | float) = "undefined",
                         exc_uncertainty_taken_from_existing_inventory: bool = False,
                         exc_scale: (int | float | None) = None,
                         exc_shape: (int | float | None) = None,
                         exc_minimum: (int | float | None) = None,
                         exc_maximum: (int | float | None) = None,
                         overwrite_existing_key_value_pairs_with_kwargs: bool = False,
                         **kwargs: dict
                         ):
    """
    Create a valid exchange dictionary for Brightway2
    
    # Read the docs 'stats_arrays' for uncertainty
    # https://stats-arrays.readthedocs.io/en/latest/
    
    Documentation for uncertainty
    "lognormal distr." and "normal distr.":
        loc = mean deviation (μ), scale = standard deviation (σ)
    
    "bernoulli distr.":
        loc = A one-row parameter array (p). If minimum and maximum are specified, p is not limited to 0 < p < 1, but instead to the interval (minimum, maximum)
    
    "weibull":
        scale = lambda (λ), shape = k
        
    "gamma":
        scale = theta (θ), shape = k
    
    "beta distr.":
        loc = alpha (α), shape = beta (β)
        
    "generalized extreme value":
        loc = mean deviation (μ), scale = standard deviation (σ), shape = epsilon (ξ)
        
    "student's T":
        loc = mean deviation (μ), scale = standard deviation (σ), shape = degrees of freedom (ν)
    
    Parameters
    ----------
    exc_name : str
        Exchange name.
    
    exc_SimaPro_name : str
        Exchange name in SimaPro standard.    

    exc_cat : tuple
        Exchange category.
        
    exc_SimaPro_cat : tuple
        Exchange category in SimaPro standard.
        For technosphere flows, the following categories are possible, based on SimaPro standard: 'Materials/Fuels', 'Electricity/heat', 'Final waste flows', 'Waste to treatment'
        For substitution flows, the following categories are possible, based on SimaPro standard: 'Avoided products'

    exc_unit : str
        Exchange unit.
    
    exc_SimaPro_unit : str | None
        Exchange unit in SimaPro standard. If it is not provided, it will be tried to backward map the unit using the 'unit' field and the mapping from Brightway.  
    
    exc_location : str
        Geography of the exchange.
    
    exc_amount : (float | int)
        Exchange amount.
    
    exc_type : str
        Exchange type. Needs to be either 'biosphere' or 'technosphere' or 'substitution'. Otherwise, a Value Error is raised.

    exc_database : str, optional
        Database to which exchange belongs to. If not specified (= None), no key will be printed to exchange dictionary. Default is None.
    
    exc_code : str, optional
        Exchange ID/code. If not specified (= None), no key will be printed to exchange dictionary. Default is None.
    
    exc_uncertainty_type : (str | int | float), optional
        Exchange uncertainty type.
        Needs to be one of the following: 'undefined', 'no uncertainty', 'lognormal distr.', 'normal distr.', 'uniform distr.', 'triangular distr.', 'bernoulli distr.', 'discrete uniform', 'weibull', 'gamma', 'beta distr.', 'generalized extreme value', 'student's T'
        Otherwise, a Type Error is raised. The default is 'undefined'.
    
    exc_uncertainty_taken_from_existing_inventory : bool, optional
        Specifies whether the current values for scale, shape, minimum, maximum are taken from an existing inventory or if they were manually provided.
        If set to True, values will be used as they are provided. If False, they will be adjusted accordingly.
    
    exc_scale : (int | float | None), optional
        Exchange scale. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_shape : (int | float | None), optional
        Exchange shape. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_minimum : (int | float | None), optional
        Exchange minimum. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_maximum : (int | float | None), optional
        Exchange maximum. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    overwrite_existing_key_value_pairs_with_kwargs : bool, optional
        Defines whether to check if key/value pairs would be overwritten by **kwargs if **kwargs are given as function inputs. The default is False.
    
    **kwargs : dict, optional
        Additional key/value pairs to be passed to the exchange.

    Returns
    -------
    exc : dict
        An exchange dictionary in valid Brightway2 format is returned.

    """
    
    # Function input variable check
    hp.check_function_input_type(create_base_exchange, locals())
    
    # Create a reversed uncertainty type mapping
    reverse_uncertainty_type_mapping = {int(v): k for k, v in uncertainty_type_mapping.items()} 
    
    # Only biosphere, substitution and technosphere strings can be provided for type
    if exc_type not in ["technosphere", "biosphere", "substitution"]:
        raise ValueError("Exchange type has wrong value. Needs to be either 'biosphere' or 'technosphere' or 'substitution' but is currently '" + str(exc_type) + "'")
    
    # The only SimaPro categories which can be used for technosphere and substitution exchanges
    # If categories other than those are used, an error is raised
    SimaPro_substitution_cats = [(v,) for k, v in SIMAPRO_SUBSTITUTION_COMPARTMENTS.items()]
    SimaPro_technosphere_cats = [(v,) for k, v in SIMAPRO_TECHNOSPHERE_COMPARTMENTS.items()]
    
    # Raise error if the category provided does not match one of the categories specified
    if exc_type == "technosphere" and exc_SimaPro_cat not in SimaPro_technosphere_cats:
        raise ValueError("The SimaPro_category provided for the technosphere exchange can not be accepted because it does not match one of the baseline SimaPro categories previously specified.\n\nCurrent category: " + str(exc_SimaPro_cat) + "\nAccepted categories: " + str(SimaPro_technosphere_cats))
    
    if exc_type == "substitution" and exc_SimaPro_cat not in SimaPro_substitution_cats:
        raise ValueError("The category provided for the substitution exchange can not be accepted because it does not match one of the baseline SimaPro categories previously specified.\n\nCurrent category: " + str(exc_SimaPro_cat) + "\nAccepted categories: " + str(SimaPro_substitution_cats))    

    # Check if the uncertainty type is of type float or int. If yes, we need to transform to str via the mapping file
    if isinstance(exc_uncertainty_type, int | float):
        
        # Check if values are in the acceptable range of 0 to 12
        if reverse_uncertainty_type_mapping.get(exc_uncertainty_type) is None:
            raise ValueError("Uncertainty type '" + str(exc_uncertainty_type) + "' needs to be one of the following numbers --> " + str(list(reverse_uncertainty_type_mapping.keys())) + ". Otherwise, it can not be mapped properly.")
        
        # Transform uncertainty type to string via the mapping file
        exc_uncertainty_type = reverse_uncertainty_type_mapping[int(exc_uncertainty_type)]
        
    # Current ID of the uncertainty type from mapping
    current_uncertainty = uncertainty_type_mapping[exc_uncertainty_type]

    # exc_loc, exc_scale, exc_shape, exc_minimum, exc_maximum
    uncertainty_dict_orig = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None,
                             "loc": exc_amount,
                             "scale": exc_scale,
                             "shape": exc_shape,
                             "minimum": exc_minimum,
                             "maximum": exc_maximum}
        
    # Raise type error if given uncertainty type is not available in the mapping
    if uncertainty_type_mapping.get(exc_uncertainty_type) is None:
        raise TypeError("Uncertainty type (= variable 'exc_uncertainty_type') is not valid: '" + str(exc_uncertainty_type) + "'\nChoose one from the list -->\n- " + str("\n  - ".join(list(uncertainty_type_mapping.keys()))))
    
    # Raise error if the current uncertainty type is not yet implemented 1) in 'LCI_builder' because 2) it is not yet implemented in Brightway2
    assert uncertainty_type_mapping[exc_uncertainty_type] <= 5, "Current uncertainty type '" + str(exc_uncertainty_type) + "' is not yet implemented in 'LCI_builder' because it is not yet implemented in Brightway and can not be used in LCA calculation."
    
    # Check if for given uncertainty type, all required fields are provided
    not_available = [m for m in required[exc_uncertainty_type] if uncertainty_dict_orig[m] is None]
    if not_available != []:
        raise TypeError("Uncertainty type '" + str(exc_uncertainty_type) + "' requires " + str(tuple(required[exc_uncertainty_type])) + " as input(s), but " + str(tuple(not_available)) + " is/are not provided.")
    

    
    # Transform values if needed
    if not exc_uncertainty_taken_from_existing_inventory:
                
        # Transform values
        uncertainty_dict = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None, 
                            "loc": math.log(abs(exc_amount)) if current_uncertainty in [2] else exc_amount,
                            "scale": math.log(math.sqrt(exc_scale)) if current_uncertainty in [2] else (math.sqrt(exc_scale) if current_uncertainty in [3] else None),
                            "shape": exc_shape,
                            "minimum": exc_minimum,
                            "maximum": exc_maximum}
        
        # Check if for given uncertainty type, all values of required fields were transformed
        not_transformed = [m for m in required[exc_uncertainty_type] if uncertainty_dict[m] is None]
        if not_transformed != []:
            raise TypeError("Transformation of values for required fields " + str(tuple(not_transformed)) + " for uncertainty type '" + str(exc_uncertainty_type) + " yielded None values/could not be done.")
    
    else:
        # Create uncertainty dictionary
        uncertainty_dict = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None, 
                            "loc": exc_amount,
                            "scale": exc_scale,
                            "shape": exc_shape,
                            "minimum": exc_minimum,
                            "maximum": exc_maximum}
    
    # Check if SimaPro unit is provided as function input
    if exc_SimaPro_unit is None:
        
        # If not, map the unit given to the SimaPro standard
        exc_SimaPro_unit_mapped = backward_unit_normalization_mapping.get(exc_unit)
        
        # If mapping has failed, raise error
        if exc_SimaPro_unit_mapped is None:
            raise ValueError("'exc_SimaPro_unit' could not be mapped from 'exc_unit'. Provide 'exc_SimaPro_unit' as function input (not using None).")
    
    
    # Initialize empty dict for the exchange
    exc = {}
    
    # Add information to exchange dictionary
    exc["name"] = exc_name
    exc["SimaPro_name"] = exc_SimaPro_name
    exc["type"] = exc_type
    exc["categories"] = exc_cat
    exc["SimaPro_categories"] = exc_SimaPro_cat
    exc["unit"] = exc_unit
    exc["SimaPro_unit"] = exc_SimaPro_unit if exc_SimaPro_unit is not None else exc_SimaPro_unit_mapped 
    exc["location"] = exc_location
    exc["amount"] = exc_amount

    # Write code and database parameters, but only if both exist (= not None)
    if exc_database is not None and exc_code is not None:
        exc["input"] = (exc_database, exc_code)        
    
    # Add uncertainty dictionary to the exchange
    exc |= dict({"uncertainty type": uncertainty_type_mapping.get(exc_uncertainty_type)}, **{k: v for k, v in uncertainty_dict.items() if v is not None})
    
    # Add additional items provided by kwargs to the exchange
    for k, v in kwargs.items():
        
        # Evaluate, if existing key/value pair would be overwritten, in case key are named equally
        if not overwrite_existing_key_value_pairs_with_kwargs and k in exc:
            
            # Throw error, if specified to NOT overwrite
            raise ValueError("Key/value pair already exists in exchange. Problematic key: '" + str(k) + "'.\n\nEither set variable 'overwrite_existing_key_value_pairs_with_kwargs' to True or make sure to NOT pass the key/value pair to the exchange via **kwargs.")
        else:
            # Otherwise, overwrite
             exc[k] = v
    
    return exc






# Function to be used to create valid Brightway2 exchanges
def create_base_exchange_from_existing_inventory(inventory_database: str,
                                                 inventory_code: str,
                                                 exc_type: str,
                                                 exc_amount: (int | float),
                                                 exc_uncertainty_type: (str | int | float) = "undefined",
                                                 exc_uncertainty_taken_from_existing_inventory: bool = False,
                                                 exc_scale: (int | float | None) = None,
                                                 exc_shape: (int | float | None) = None,
                                                 exc_minimum: (int | float | None) = None,
                                                 exc_maximum: (int | float | None) = None,
                                                 overwrite_existing_key_value_pairs_with_kwargs: bool = False,
                                                 **kwargs: dict
                                                 ):
    """
    Create a valid exchange dictionary for Brightway2 from an existing, registered Brightway2 inventory.
    
    # Read the docs 'stats_arrays' for uncertainty
    # https://stats-arrays.readthedocs.io/en/latest/
    
    Documentation for uncertainty
    "lognormal distr." and "normal distr.":
        loc = mean deviation (μ), scale = standard deviation (σ)
    
    "bernoulli distr.":
        loc = A one-row parameter array (p). If minimum and maximum are specified, p is not limited to 0 < p < 1, but instead to the interval (minimum, maximum)
    
    "weibull":
        scale = lambda (λ), shape = k
        
    "gamma":
        scale = theta (θ), shape = k
    
    "beta distr.":
        loc = alpha (α), shape = beta (β)
        
    "generalized extreme value":
        loc = mean deviation (μ), scale = standard deviation (σ), shape = epsilon (ξ)
        
    "student's T":
        loc = mean deviation (μ), scale = standard deviation (σ), shape = degrees of freedom (ν)
    
    Parameters
    ----------
    inventory_database : str
        Database where the inventory for the exchange should be retrieved from.
    
    inventory_code : str
        The code of the inventory that should be retrieved.
    
    exc_type : str
        Exchange type. Needs to be either 'biosphere' or 'technosphere' or 'substitution'. Otherwise, a Value Error is raised.

    exc_amount : (float | int)
        Exchange amount.
    
    exc_uncertainty_type : (str | int | float), optional
        Exchange uncertainty type.
        Needs to be one of the following: 'undefined', 'no uncertainty', 'lognormal distr.', 'normal distr.', 'uniform distr.', 'triangular distr.', 'bernoulli distr.', 'discrete uniform', 'weibull', 'gamma', 'beta distr.', 'generalized extreme value', 'student's T'
        Otherwise, a Type Error is raised. The default is 'undefined'.
    
    exc_uncertainty_taken_from_existing_inventory : bool, optional
        Specifies whether the current values for scale, shape, minimum, maximum are taken from an existing inventory or if they were manually provided.
        If set to True, values will be used as they are provided. If False, they will be adjusted accordingly.
    
    exc_scale : (int | float | None), optional
        Exchange scale. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_shape : (int | float | None), optional
        Exchange shape. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_minimum : (int | float | None), optional
        Exchange minimum. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    exc_maximum : (int | float | None), optional
        Exchange maximum. Needed for certain uncertainty types. Have a look at the 'stats_arrays' documentation. The default is None (= not provided).
    
    overwrite_existing_key_value_pairs_with_kwargs : bool, optional
        Defines whether to check if key/value pairs would be overwritten by **kwargs if **kwargs are given as function inputs. The default is False.
    
    **kwargs : dict, optional
        Additional key/value pairs to be passed to the exchange.

    Returns
    -------
    exc : dict
        An exchange dictionary in valid Brightway2 format is returned.

    """
    
    # Function input variable check
    hp.check_function_input_type(create_base_exchange, locals())
    
    # Create a reversed uncertainty type mapping
    reverse_uncertainty_type_mapping = {int(v): k for k, v in uncertainty_type_mapping.items()} 
    
    # Only biosphere, substitution and technosphere strings can be provided for type
    if exc_type not in ["technosphere", "biosphere", "substitution"]:
        raise ValueError("Exchange type has wrong value. Needs to be either 'biosphere' or 'technosphere' or 'substitution' but is currently '" + str(exc_type) + "'")
    
    # The only SimaPro categories which can be used for technosphere and substitution exchanges
    # If categories other than those are used, an error is raised
    SimaPro_substitution_cats = [(v,) for k, v in SIMAPRO_SUBSTITUTION_COMPARTMENTS.items()]
    SimaPro_technosphere_cats = [(v,) for k, v in SIMAPRO_TECHNOSPHERE_COMPARTMENTS.items()]

    # Check if the uncertainty type is of type float or int. If yes, we need to transform to str via the mapping file
    if isinstance(exc_uncertainty_type, int | float):
        
        # Check if values are in the acceptable range of 0 to 12
        if reverse_uncertainty_type_mapping.get(exc_uncertainty_type) is None:
            raise ValueError("Uncertainty type '" + str(exc_uncertainty_type) + "' needs to be one of the following numbers --> " + str(list(reverse_uncertainty_type_mapping.keys())) + ". Otherwise, it can not be mapped properly.")
        
        # Transform uncertainty type to string via the mapping file
        exc_uncertainty_type = reverse_uncertainty_type_mapping[int(exc_uncertainty_type)]
        
    # Current ID of the uncertainty type from mapping
    current_uncertainty = uncertainty_type_mapping[exc_uncertainty_type]

    # exc_loc, exc_scale, exc_shape, exc_minimum, exc_maximum
    uncertainty_dict_orig = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None,
                             "loc": exc_amount,
                             "scale": exc_scale,
                             "shape": exc_shape,
                             "minimum": exc_minimum,
                             "maximum": exc_maximum}
        
    # Raise type error if given uncertainty type is not available in the mapping
    if uncertainty_type_mapping.get(exc_uncertainty_type) is None:
        raise TypeError("Uncertainty type (= variable 'exc_uncertainty_type') is not valid: '" + str(exc_uncertainty_type) + "'\nChoose one from the list -->\n- " + str("\n  - ".join(list(uncertainty_type_mapping.keys()))))
    
    # Raise error if the current uncertainty type is not yet implemented 1) in 'LCI_builder' because 2) it is not yet implemented in Brightway2
    assert uncertainty_type_mapping[exc_uncertainty_type] <= 5, "Current uncertainty type '" + str(exc_uncertainty_type) + "' is not yet implemented in 'LCI_builder' because it is not yet implemented in Brightway and can not be used in LCA calculation."
    
    # Check if for given uncertainty type, all required fields are provided
    not_available = [m for m in required[exc_uncertainty_type] if uncertainty_dict_orig[m] is None]
    if not_available != []:
        raise TypeError("Uncertainty type '" + str(exc_uncertainty_type) + "' requires " + str(tuple(required[exc_uncertainty_type])) + " as input(s), but " + str(tuple(not_available)) + " is/are not provided.")
    
    # Transform values if needed
    if not exc_uncertainty_taken_from_existing_inventory:
                
        # Transform values
        uncertainty_dict = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None, 
                            "loc": math.log(abs(exc_amount)) if current_uncertainty in [2] else exc_amount,
                            "scale": math.log(math.sqrt(exc_scale)) if current_uncertainty in [2] else (math.sqrt(exc_scale) if current_uncertainty in [3] else None),
                            "shape": exc_shape,
                            "minimum": exc_minimum,
                            "naximum": exc_maximum}
        
        # Check if for given uncertainty type, all values of required fields were transformed
        not_transformed = [m for m in required[exc_uncertainty_type] if uncertainty_dict[m] is None]
        if not_transformed != []:
            raise TypeError("Transformation of values for required fields " + str(tuple(not_transformed)) + " for uncertainty type '" + str(exc_uncertainty_type) + " yielded None values/could not be done.")
    
    else:
        # Create uncertainty dictionary
        uncertainty_dict = {"negative": exc_amount < 0 if current_uncertainty in [2, 3, 4, 5] else None, 
                            "loc": exc_amount,
                            "scale": exc_scale,
                            "shape": exc_shape,
                            "minimum": exc_minimum,
                            "maximum": exc_maximum}
    
    # Retrieve information from existing inventory
    ds = bw2data.Database(inventory_database).get(inventory_code)
    
    # Initialize empty dict for the exchange
    exc = {}
    
    # Add information to exchange dictionary
    exc["name"] = ds["name"]
    exc["SimaPro_name"] = ds["SimaPro_name"]
    exc["type"] = exc_type
    exc["categories"] = ds["SimaPro_categories"]
    exc["SimaPro_categories"] = ds["SimaPro_categories"]
    exc["unit"] = ds["unit"]
    exc["SimaPro_unit"] = ds["SimaPro_unit"]
    exc["location"] = ds["location"]
    exc["amount"] = exc_amount
    exc["input"] = (inventory_database, inventory_code)
    
    # Add uncertainty dictionary to the exchange
    exc |= dict({"uncertainty type": uncertainty_type_mapping.get(exc_uncertainty_type)}, **{k: v for k, v in uncertainty_dict.items() if v is not None})
    
    # Add additional items provided by kwargs to the exchange
    for k, v in kwargs.items():
        
        # Evaluate, if existing key/value pair would be overwritten, in case key are named equally
        if not overwrite_existing_key_value_pairs_with_kwargs and k in exc:
            
            # Throw error, if specified to NOT overwrite
            raise ValueError("Key/value pair already exists in exchange. Problematic key: '" + str(k) + "'.\n\nEither set variable 'overwrite_existing_key_value_pairs_with_kwargs' to True or make sure to NOT pass the key/value pair to the exchange via **kwargs.")
        else:
            # Otherwise, overwrite
             exc[k] = v
    
    return exc

