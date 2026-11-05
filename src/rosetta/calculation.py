import pathlib

import ast
import datetime
import bw2calc
import bw2data
import numpy as np
import pandas as pd
from bw2calc.errors import OutsideTechnosphere
from . import _helpers as hp


#%%

class LCACalculation:
    
    def __init__(self,
                 activities: list,
                 methods: list,
                 functional_amount: (float | int) = 1,
                 cut_off_percentage: (float | int | None) = None,
                 exchange_level: int = 1,
                 print_progress_bar: bool = True) -> None:
        
        """ A class that provides functions to do fast and efficient LCA calculations in Brightway2
        Only the list of LCI activities and the LCIA methods need to be supplied.
        
        
        Parameters
        ----------
        activities : list
            A list of activities (LCI) (in Brightway format, as activity objects retrieved from background databases) for which impacts should be calculated.
            
        methods : list
            A list of LCIA methods (in Brightway format, as tuple) which should be used for impact assessment of the inventories.
            Methods need to be registered in the Brightway background in order to work.
            
        functional_amount : (float | int)
            Indicates the reference unit of the calculated environmental impacts. Refers to how much of an activity should be calculated.
            With value of 1, it will calculate/retrieve information for 1 unit of the activity.
            The default is 1.
        
        cut_off_percentage : (float | int | None)
            Will only be applied in case LCIA emission contribution and LCIA process contribution are calculated. The value needs to be between 0 and 1.
            When a percentage is indicated (not None), the list of contributing emissions or processes will be shortened.
            The higher the percentage, the higher the cut off for scores and therefore the shorter the list.
            Impacts that are cut will be summarised into a 'Rest' value.
            The default is None (no cut off applied).
            
        exchange_level : int
            Needs to be >= 1 in order to work. Specifies at which level/tier the exchanges of an activity should be extracted from.
            The higher the level, the more exchanges and the longer the calculation will take.
            Important: for emissions, there are no subsequent levels. It would be wrong to just avoid them. That's why for emissions the level might be smaller than what is specified here.
            The default is 1.
        
        print_progress_bar : bool
            Specifies whether to print a progress bar to the console indicating the progress of the calculation
            
        """
        
        
        # Check function input type
        hp.check_function_input_type(self.__init__, locals())
        
        # Check if activities are all Brightway activity objects
        check_activities = [m for m in activities if not isinstance(m, bw2data.backends.peewee.proxies.Activity)]
        
        # Check and raise error
        if check_activities != []:
            raise ValueError("Input variable 'activities' needs to be a list of only Activity objects.")
            
        # Check if methods are all tuples
        assert all([isinstance(m, tuple) for m in methods]), "At least one method is not of type <tuple>."
        
        # Extract all methods that are not registered in the Brightway background
        check_methods = [str(m) for m in methods if m not in bw2data.methods]
        
        # Check if all methods are registered in the Brightway background
        if check_methods != []:
            raise ValueError("They following methods are not registered:\n - " + "\n - ".join(check_methods))
        
        # Raise error if level is smaller than 1
        if exchange_level < 1:
            raise ValueError("Input variable 'exchange_level' needs to be greater than 1 but is currently '" + str(exchange_level) + "'.")
        
        # Raise error if the cut off is not between 0 and 1
        if cut_off_percentage is not None and (cut_off_percentage < 0 or cut_off_percentage > 1):
            raise ValueError("Input variable 'cut_off_percentage' needs to be between 0 and 1 but is currently '" + str(cut_off_percentage) + "'.")
        
        # Loop through each activity and construct the key tuple if not yet existing
        for activity in activities:
            
            # Check if the key is already existing
            if not hasattr(activity, "key"):
                
                # Extract key components, database and code
                database: (str | None) = activity["database"]
                code: (str | None) = activity["code"]
                
                # Raise error if they were not found
                if database is None or code is None:
                    raise ValueError("Activity key tuple could not be constructed.")
                
                # Add key attribute
                activity.key: tuple[str, str] = (database, code)
        
        # The functional unit is defined as 1
        self.functional_amount: (int | float) = functional_amount
        
        # Add to object
        self.activities: list[bw2data.backends.peewee.proxies.Activity] = activities
        self.methods: list[tuple] = methods
        self.cut_off_percentage: (int | float) = cut_off_percentage
        self.exchange_level: int = exchange_level
        self.progress_bar: bool = print_progress_bar
        
        # Defaults
        self.rest_key: tuple = (None, None)
        self.rest_name: str = "Rest"
        
        # Definition of names to be used for the different results
        self.name_LCIA_scores: str = "LCIA_scores"
        self.name_LCIA_immediate_scores: str = "LCIA_scores_of_exchanges"
        self.name_LCI_exchanges: str = "LCI_exchanges"
        self.name_LCI_emission_contributions: str = "LCI_emission_contribution"
        self.name_LCI_process_contributions: str = "LCI_process_contribution"
        self.name_LCIA_emission_contributions: str = "LCIA_emission_contribution"
        self.name_LCIA_process_contributions: str = "LCIA_process_contribution"
        self.name_characterization_factors: str = "Characterization_factors"
        
        self.activities_as_dict: dict = {}
        self.database_objects: dict = {}
        self.method_objects: dict = {}
        self.method_units: dict = {}
        self.characterization_factors: dict = {}
        self.lca_objects: dict = {} # almost everywhere
        self.characterization_matrices: dict = {} # LCIA score, LCIA emission contr., LCIA process contr.
        self.biosphere_dicts_as_arrays: dict = {} # LCI emission contr., LCIA emission contr.
        self.activity_dicts_as_arrays: dict = {} # LCI process contr., LCIA process contr.
        self.element_arrays: dict = {} # all contributions, LCI & LCIA, emission & process
        self.structured_arrays_for_emission_contribution: dict = {} # LCI emission contr, LCIA emission contr.
        self.structured_arrays_for_process_contribution: dict = {} # LCI process contr, LCIA process contr.
        self.method_arrays_for_LCIA_emission_contribution: dict = {} # LCIA emission contr.
        self.method_arrays_for_LCIA_process_contribution: dict = {} # LCIA process contr.
        self._temporary_key_to_exchanges_mapping: dict = {}
        self._temporary_score_results: dict = {}
        
        # Keys to extract from the activity dicts
        self.keys_to_extract_from_BW_acts: tuple[str] = ("name",
                                                         "SimaPro_name",
                                                         "categories",
                                                         "location",
                                                         "unit")
        
        # Names to give when mapping
        self._act_k_name: str = "Activity"
        self._flow_k_name: str = "Flow"
        self._score_k_name: str = "Score"
        self._method_k_name: str = "Method"
        self._cf_k_name: str = "Characterization_Factor"
        self._name_sep: str = "_"
        
        # Specific column names
        self.k_act_database: str = self._name_sep.join((self._act_k_name, "database"))
        self.k_act_code: str = self._name_sep.join((self._act_k_name, "code"))
        self.k_act_amount: str = self._name_sep.join((self._act_k_name, "amount"))
        self.k_flow_database: str = self._name_sep.join((self._flow_k_name, "database"))
        self.k_flow_code: str = self._name_sep.join((self._flow_k_name, "code"))
        self.k_flow_amount: str = self._name_sep.join((self._flow_k_name, "amount"))
        
    
    def _get_database_object(self, database: str) -> bw2data.Database:
        
        # Simply return, if already existing
        if self.database_objects.get(database) is not None:
            return self.database_objects[database]
        
        # Initialize the object
        obj: bw2data.Database = bw2data.Database(database)
        
        # Add to dictionary, temporarily
        self.database_objects[database]: bw2data.Database = obj
        
        # Return the object
        return obj
    
    
    def _get_method_object(self, method: tuple[str]) -> bw2data.Method:
        
        # Simply return, if already existing
        if self.method_objects.get(method) is not None:
            return self.method_objects[method]
        
        # Initialize the object
        obj: bw2data.Method = bw2data.Method(method)
        
        # Add to dictionary, temporarily
        self.method_objects[method]: bw2data.Method = obj
        
        # Return the object
        return obj
    
    
    def _get_method_unit(self, method: tuple[str]) -> str:
        
        # Simply return, if already existing
        if self.method_units.get(method) is not None:
            return self.method_units[method]
        
        # Get or initialize the method object
        method_obj: bw2data.Method = self._get_method_object(method = method)
        method_unit: str = method_obj.metadata["unit"]

        # Add to dictionary, temporarily
        self.method_units[method]: str = method_unit
        
        # Return the method unit as string
        return method_unit
    
    
    def _load_characterization_factors(self, method: tuple[str]) -> None:
        
        # Simply return, if already existing
        if self.characterization_factors.get(method) is not None:
            return
        
        # Get method object
        method_obj: bw2data.Method = self._get_method_object(method = method)
        
        # Initialize a new method dictionary
        self.characterization_factors[method]: dict[tuple, dict[tuple[str, str], float]] = {}
        
        # Loop through each characterization factor for each flow individually
        for key, cf in method_obj.load():
            
            # Check if key exists, if not create one with a 0 amount
            if self.characterization_factors[method].get(key) is None:
                self.characterization_factors[method][key]: float = float(0)
                
            # Add to the existing CF
            self.characterization_factors[method][key] += cf
           
            
    def _get_characterization_factor(self, method: tuple[str], key: tuple[str, str]) -> (float | None):
        
        # Load method if not yet loaded
        self._load_characterization_factors(method = method)
        
        # Return the characterization factor
        return self.characterization_factors[method].get(key)
    
    
    def _get_act_as_dict(self, act_key: tuple[str, str], keys_to_extract: (tuple[str] | None) = None) -> dict:
        
        # Simply return, if already existing
        if self.activities_as_dict.get(act_key) is not None:
            return self.activities_as_dict[act_key]
        
        # Retrieve the activity object
        act = self._get_database_object(database = act_key[0]).get(act_key[1])
        
        # Extract the relevant keys, or if None is specified, the whole dictionary
        act_as_dict: dict = {i: act.get(i) for i in keys_to_extract} if keys_to_extract is not None else act.as_dict()
        
        # Save the dict temporarily
        self.activities_as_dict[act_key]: dict = act_as_dict
        
        # Return the dictionary
        return act_as_dict
    
    
    def _get_LCA_object(self, database: str) -> bw2calc.lca.LCA:
        
        # Simply return, if already existing
        if self.lca_objects.get(database) is not None:
            return self.lca_objects[database]
        
        # Extract first inventory and method to then initialise lca object
        _act: bw2data.backends.peewee.proxies.Activity = self._get_database_object(database = database).random()
        _met: tuple = self.methods[0]
        
        # LCA object generation will fail for biosphere databases
        # However, we do not need an LCA object for biosphere databases but only the characterization factors
        
        # Create the Brightway2 LCA object from the first activity and method.
        # This takes a little bit long, and therefore this step is only done once. The object will be reused in the calculation            
        lca_object: bw2calc.lca.LCA = bw2calc.LCA({_act.key: self.functional_amount}, method = _met)
        
        # Calculate inventory once to load all database data
        lca_object.lci()
        
        # Load method data 
        lca_object.lcia()
        
        # Append to dictionary and initialize a dictionary to store the characterized matrices to
        self.lca_objects[database]: bw2calc.lca.LCA = lca_object
        self.characterization_matrices[database]: dict = {}
        
        # Loop through each method to build the characterization matrices
        for met in self.methods:
            
            # Switch to new method
            lca_object.switch_method(met)
            
            # Extract the characterization matrix and write to dictionary
            self.characterization_matrices[database][met] = lca_object.characterization_matrix.copy()
        
        # Return the lca object
        return self.lca_objects[database]
    
    
    def _get_characterization_matrix(self, database: str, method: str):
        
        # Simply return if already existing
        if self.characterization_matrices.get(database) is not None:
            return self.characterization_matrices[database][method]

        # Otherwise, create BW object and matrices
        self._get_LCA_object(database = database)
        
        # Return the matrix
        return self.characterization_matrices[database][method]
    
    
    
    def _get_biosphere_dict_as_array(self, database: str) -> np.array:
        
        # Simply return if already existing
        if self.biosphere_dicts_as_arrays.get(database) is not None:
            return self.biosphere_dicts_as_arrays[database]
        
        # Retrieve the lca object
        lca_object: bw2calc.lca.LCA = self._get_LCA_object(database = database)
        
        # Write the biosphere dict as array
        biosphere_array: np.array = np.array([str(m) for m in lca_object.biosphere_dict.keys()], dtype = "U")
        
        # Temporarily store
        self.biosphere_dicts_as_arrays[database]: np.array = biosphere_array
        
        # Return the array
        return biosphere_array
    
    
    
    def _get_activity_dict_as_array(self, database: str) -> np.array:
        
        # Simply return if already existing
        if self.activity_dicts_as_arrays.get(database) is not None:
            return self.activity_dicts_as_arrays[database]
        
        # Retrieve the lca object
        lca_object: bw2calc.lca.LCA = self._get_LCA_object(database = database)
        
        # Write the activity dict as array
        activity_array: np.array = np.array([str(m) for m in lca_object.activity_dict.keys()], dtype = "U")
        
        # Temporarily store
        self.activity_dicts_as_arrays[database]: np.array = activity_array
        
        # Return the array
        return activity_array
    
    
    def _get_element_array(self, element: (str | None | tuple), length: int, dtype: (str | None)) -> np.array:
        
        # Simply return if already existing
        if self.element_arrays.get((element, length, dtype)) is not None:
            return self.element_arrays[(element, length, dtype)]
        
        # Construct an array with only elements and length indicated
        element_array: np.array = np.array([element] * length, dtype = dtype)
        
        # Add the matrix to the temporary dict
        self.element_arrays[(element, length, dtype)]: np.array = element_array
        
        # Return the matrix
        return element_array
    
    
    def _apply_cut_off_to_structured_array(self, structured_array: np.array, cut_off: (float | None)) -> np.array:
        
        # Exclude all values that are 0
        array: np.array = structured_array[structured_array["value"] != 0]
        
        # If no cutoff is specified, simply return the array. We don't need to go on
        if cut_off is None:
            return array
        
        # If the array is empty, return
        if len(array) == 0:
            return array
        
        # Temporarily save the last row
        last: tuple = tuple(array[-1:])
        
        # Select (= mask) all values that are above and below 0
        mask_under_0: np.array = array["value"] < 0
        mask_over_0: np.array = array["value"] > 0
        
        # Retrieve the arrays with values above and below 0, separately
        under_0: np.array = array[mask_under_0]
        over_0: np.array = array[mask_over_0]
        
        # Identify the limit/treshold from where on values will be excluded
        # We do the sum and then multiply it with the cut off indicated
        min_treshold = sum(under_0["value"]) * cut_off
        max_treshold = sum(over_0["value"]) * cut_off
        
        # Select arrays again, only containing the values that are not excluded by the cut off
        mask_min_treshold = under_0["value"] < min_treshold
        mask_max_treshold = over_0["value"] > max_treshold
        
        # Retrieve the rest amount as a sum of everything that was excluded
        rest_amount = sum(under_0["value"][~mask_min_treshold]) + sum(over_0["value"][~mask_max_treshold])
        
        # Construct a tuple for the rest
        updated_last: tuple = (last[0][0],
                               last[0][1],
                               str(self.rest_key),
                               None,
                               rest_amount,
                               last[0][5]
                               )
        # Write the rest as array
        rest: np.array = np.array([updated_last], dtype = structured_array.dtype)
        
        # Add all together
        constructed = np.concatenate((over_0[mask_max_treshold], under_0[mask_min_treshold], rest), axis = 0)
        
        # Return
        return constructed
    
    
    
    def _get_structured_array_for_LCI_emission_contribution(self, database: str) -> np.array:
        
        # If already existing, simply return
        if self.structured_arrays_for_emission_contribution.get(database) is not None:
            return self.structured_arrays_for_emission_contribution[database][None]
        
        # Get the biosphere dictionary as an array
        biosphere_array: np.array = self._get_biosphere_dict_as_array(database = database)
        
        # Extract the length of the array, since everything needs to be at this length
        length_biosphere_array: int = biosphere_array.shape[0]
        
        # Construct an array with only the None's and the length of the biosphere array
        none_array: np.array = self._get_element_array(element = None, length = length_biosphere_array, dtype = object)
        
        # Construct an array with the functional amount and the length of the biosphere array
        functional_amount_array: np.array = self._get_element_array(element = self.functional_amount, length = length_biosphere_array, dtype = "float64")
        functional_amount_array_dtype = functional_amount_array.dtype
        
        # Construct a placeholder array with a random activity key and the length of the biosphere array
        # Note that storing a tuple in an array would be doable, but we then run into issues converting it back
        # That's why we cast the tuple to a string first
        activity_key_array: np.array = self._get_element_array(element = str(self.activities[0].key), length = length_biosphere_array, dtype = "U")
        
        # Extract the array type from the inventory
        inventory_dtype = self._get_LCA_object(database = database).inventory.dtype
        
        # Construct a 0 array for the values (this one will be overwritten later)
        value_array: np.array = np.zeros(length_biosphere_array, dtype = inventory_dtype)
        
        # Construct dtypes for the structured array
        dtype: list[tuple] = [("activity_key", activity_key_array.dtype),
                              ("functional_amount", functional_amount_array_dtype),
                              ("flow_key", biosphere_array.dtype),
                              ("flow_amount", none_array.dtype),
                              ("value", inventory_dtype),
                              ("method", none_array.dtype)
                              ]
                
        # Build structured array and add to dictionary
        self.structured_arrays_for_emission_contribution[database]: dict[(tuple | None), np.array] = {None: np.core.records.fromarrays([activity_key_array,
                                                                                                                                        functional_amount_array,
                                                                                                                                        biosphere_array,
                                                                                                                                        none_array,
                                                                                                                                        value_array,
                                                                                                                                        none_array
                                                                                                                                        ], dtype = dtype)}
        
        # Return
        return self.structured_arrays_for_emission_contribution[database][None]
    
    
    def _get_structured_array_for_LCI_process_contribution(self, database: str) -> np.array:
        
        # If already existing, simply return
        if self.structured_arrays_for_process_contribution.get(database) is not None:
            return self.structured_arrays_for_process_contribution[database][None]
        
        # Get the activity dictionary as an array
        activity_array: np.array = self._get_activity_dict_as_array(database = database)
        
        # Extract the length of the array, since everything needs to be at this length
        length_activity_array: int = activity_array.shape[0]
        
        # Construct an array with only the None's and the length of the activity array
        none_array: np.array = self._get_element_array(element = None, length = length_activity_array, dtype = object)
        
        # Construct an array with the functional amount and the length of the activity array
        functional_amount_array: np.array = self._get_element_array(element = self.functional_amount, length = length_activity_array, dtype = "float64")
        functional_amount_array_dtype = functional_amount_array.dtype
        
        # Construct a placeholder array with a random activity key and the length of the activity array
        # Note that storing a tuple in an array would be doable, but we then run into issues converting it back
        # That's why we cast the tuple to a string first
        activity_key_array: np.array = self._get_element_array(element = str(self.activities[0].key), length = length_activity_array, dtype = "U")
        
        # Extract the array type from the inventory
        inventory_dtype = self._get_LCA_object(database = database).inventory.dtype
        
        # Construct a 0 array for the values (this one will be overwritten later)
        value_array: np.array = np.zeros(length_activity_array, dtype = inventory_dtype)
        
        # Construct dtypes for the structured array
        dtype: list[tuple] = [("activity_key", activity_key_array.dtype),
                              ("functional_amount", functional_amount_array_dtype),
                              ("flow_key", activity_array.dtype),
                              ("flow_amount", none_array.dtype),
                              ("value", inventory_dtype),
                              ("method", none_array.dtype)
                              ]
                
        # Build structured array and add to dictionary
        self.structured_arrays_for_process_contribution[database]: dict[(tuple | None), np.array] = {None: np.core.records.fromarrays([activity_key_array,
                                                                                                                                       functional_amount_array,
                                                                                                                                       activity_array,
                                                                                                                                       none_array,
                                                                                                                                       value_array,
                                                                                                                                       none_array
                                                                                                                                       ], dtype = dtype)}
        
        # Return
        return self.structured_arrays_for_process_contribution[database][None]
        
        
        
    def _get_structured_array_for_LCIA_emission_contribution(self, database: str, method: tuple) -> np.array:
        
        # If already existing, simply return
        if self.structured_arrays_for_emission_contribution.get(database, {}).get(method) is not None:
            return self.structured_arrays_for_emission_contribution[database][method]
        
        # Retrieve or build the initial structured emission array
        structured_LCI_emission_array: np.array = self._get_structured_array_for_LCI_emission_contribution(database = database).copy() # !!! We need this copy right now, but it slows calculation down. Alternative?
    
        # Overwrite the method array (None's) with the method
        structured_LCI_emission_array["method"]: np.array = self._get_element_array(element = str(method), length = len(structured_LCI_emission_array["value"]), dtype = "U")
    
        # Add temporarily
        self.structured_arrays_for_emission_contribution[database][method]: np.array = structured_LCI_emission_array.copy() 
        
        # Return
        return structured_LCI_emission_array
    
    
    
    def _get_structured_array_for_LCIA_process_contribution(self, database: str, method: tuple) -> np.array:
        
        # If already existing, simply return
        if self.structured_arrays_for_process_contribution.get(database, {}).get(method) is not None:
            return self.structured_arrays_for_process_contribution[database][method]
        
        # Retrieve or build the initial structured process array
        structured_LCI_process_array: np.array = self._get_structured_array_for_LCI_process_contribution(database = database).copy() # !!! We need this copy right now, but it slows calculation down. Alternative?
    
        # Overwrite the method array (None's) with the method
        structured_LCI_process_array["method"]: np.array = self._get_element_array(element = str(method), length = len(structured_LCI_process_array["value"]), dtype = "U")
    
        # Add temporarily
        self.structured_arrays_for_process_contribution[database][method]: np.array = structured_LCI_process_array
        
        # Return
        return self.structured_arrays_for_process_contribution[database][method]
    
    
    
    # Function to retrieve the exchanges of an activity
    def _get_exchanges(self,
                      activity_key: tuple[str, str],
                      activity_amount: float,
                      level: (int | float)) -> tuple[tuple[tuple[str, str], float, (float | int)]]:
        
        # Try to retrieve first from temporary dictionary and if successful directly return
        if self._temporary_key_to_exchanges_mapping.get(activity_key) is not None:
            
            # Directly return
            return tuple([(m[0], m[1] * activity_amount, level) for m in self._temporary_key_to_exchanges_mapping[activity_key]])
        
        # Retrieve activity
        act: bw2data.backends.peewee.proxies.Activity = self._get_database_object(database = activity_key[0]).get(activity_key[1])
        
        # Retrieve list of exchanges
        exchanges: bw2data.backends.pewee.proxies.Exchanges = act.exchanges()
        
        # Check the length of the exchanges list
        if len(exchanges) == 0:
            
            # If it is 0, the current activity is of type biosphere. We return an empty list
            return ()
        
        # Get the production amount from the list of exchanges
        production_amount: list[float] = [m["amount"] for m in exchanges if m["type"] == "production"]
        
        # Raise error if no or more than one production exchange was found.
        if len(production_amount) != 1:
            raise ValueError("The list of exchanges for activity '{}' contains {} production exchange(s).".format(activity_key, len(production_amount)))
        
        # Calibrate exchange values to 1 activity amount
        exchanges_for_1_activity_amount: list[tuple] = [(m["input"], (1 / production_amount[0] * m["amount"]) if production_amount != 0 else 0) for m in exchanges if m["type"] != "production"]
        
        # Add temporarily
        self._temporary_key_to_exchanges_mapping[activity_key]: list[tuple] = exchanges_for_1_activity_amount
        
        # Return
        return tuple([(m[0], m[1] * activity_amount, level) for m in self._temporary_key_to_exchanges_mapping[activity_key]])
        
    
    
    
    # Support function to extract exchanges of an activity based on a specific level
    def _extract_LCI_exchanges_of_activity_at_certain_level(self,
                                                            activity_key: bw2data.backends.peewee.proxies.Activity,
                                                            level: int) -> list[dict]:
        
        # Define the starting level
        current_level: int = 0

        # Initialize a new key to write exchange keys to that should be calculated in the next round
        exchanges_at_level: dict = {current_level: ((activity_key, self.functional_amount, 0),)}
        
        # Extract exchanges as long/as many times as there are levels
        while current_level < level:

            # Extract all the relevant keys at the current level
            current_exchanges: tuple[tuple, float] = exchanges_at_level[current_level]
            
            # Initialize a new list for the current level
            exchanges_at_level[current_level + 1]: tuple = ()
            
            # Loop through each current exchange key and amount
            for current_key, current_amount, respective_level in current_exchanges:
                
                # Check if the level of the current exchange matches the current level where we are, otherwise we don't need to go on and can simply move the exchange to the next round
                if respective_level < current_level:
                    
                    # Simply move the exchange to the next round without searching
                    exchanges_at_level[current_level + 1] += ((current_key, current_amount, respective_level),)
                
                else:
                    # Extract all exchanges that come next for the current exchange
                    next_exchanges: tuple[tuple] = self._get_exchanges(activity_key = current_key,
                                                                       activity_amount = current_amount,
                                                                       level = current_level + 1)
                    
                    # If no next exchanges have been found, add the current exchange
                    if len(next_exchanges) == 0:
                        
                        # Add current exchange
                        exchanges_at_level[current_level + 1] += ((current_key, current_amount, respective_level),)
                    else:
                        # Otherwise, add the new exchanges
                        exchanges_at_level[current_level + 1] += next_exchanges
                
            # Check if we arrived at the end
            if current_level >= level:
                break
                
            else:
                # Raise iterator
                current_level += 1
        
        # Initialize a new list to store final exchanges to
        exchanges_at_level_cleaned: dict = {}
        
        # Loop through each exchange
        for flow_key, flow_amount, level in exchanges_at_level[max(list(exchanges_at_level.keys()))]:
            
            # Compile the ID tuple
            ID: tuple = (
                activity_key,
                self.functional_amount,
                flow_key
                )
            
            # Initialize new key
            if exchanges_at_level_cleaned.get(ID) is None:
                exchanges_at_level_cleaned[ID]: float = float(0)
            
            # Add the amount
            exchanges_at_level_cleaned[ID] += flow_amount
            
        # Return
        return [k + (v, None, None) for k, v in exchanges_at_level_cleaned.items()]
    
    
        
    def calculate(self,
                  calculate_LCIA_scores: bool = True,
                  extract_LCI_exchanges: bool = False,
                  extract_LCI_emission_contribution: bool = False,
                  extract_LCI_process_contribution: bool = False,
                  calculate_LCIA_scores_of_exchanges: bool = False,
                  calculate_LCIA_emission_contribution: bool = False,
                  calculate_LCIA_process_contribution: bool = False):
        
        # Add an instance where results will be saved to
        self.results_raw: dict = {self.name_LCIA_scores: [],
                                  self.name_LCI_exchanges: [],
                                  self.name_LCI_emission_contributions: [],
                                  self.name_LCI_process_contributions: [],
                                  self.name_LCIA_immediate_scores: [],
                                  self.name_LCIA_emission_contributions: [],
                                  self.name_LCIA_process_contributions: []
                                  }
        
        # Save time when calculation starts
        if self.progress_bar:
            start_round_1: datetime.datetime = datetime.datetime.now()
        
        # Retrieve the combinations that should be calculated
        activities: list = self.activities
        
        # Check if progress bar should be printed to console
        if self.progress_bar:
            
            # Wrap progress bar around iterator
            activities: list = hp.progressbar(activities, prefix = "\nCalculate ...")
        
        # Loop through all activities
        for act in activities:
            
            # Extract the activity key
            activity_key: tuple[str, str] = act.key
            
            # First get the database the activity belongs to
            database: str = activity_key[0]

            # This block is needed for any calculation
            # We at least need
            # ... to get 1) the BW object,
            lca_object: bw2calc.lca.LCA = self._get_LCA_object(database = database)

            # ... to redo 2) the inventory matrix (which takes quite some time)
            lca_object.redo_lci({act: self.functional_amount})
            
            # We then extract the inventory matrix
            inventory: np.matrix = lca_object.inventory
            
            # Extract LCI exchanges, if specified
            # We also need to extract the exchanges if we calculate the immediate scores
            if any((extract_LCI_exchanges, calculate_LCIA_scores_of_exchanges)):
                
                # Extract the LCI exchanges
                LCI_exchanges_at_level: list[tuple] = self._extract_LCI_exchanges_of_activity_at_certain_level(activity_key = activity_key, level = self.exchange_level)
                
                # Add
                if extract_LCI_exchanges:
                    self.results_raw[self.name_LCI_exchanges] += LCI_exchanges_at_level
            
            
            # If we need to do any LCIA calculation, we need to do the following block
            # This however will only be done for LCIA score calculation, LCIA emission contribution and LCIA process contribution
            if any([calculate_LCIA_scores, calculate_LCIA_emission_contribution, calculate_LCIA_process_contribution]):
                
                # Initialize a temporary dictionary to store the characterized matrices to
                characterized_matrices: dict = {}
                
                # Loop through each method and create the characterized matrices by multiplying the inventory matrix with the 
                for met in self.methods:
                    
                    # Build or simply get the matrix
                    matrix = self._get_characterization_matrix(database = database, method = met)
                    
                    # Multiply the matrices
                    characterized_matrices[met] = (matrix * inventory)
            
            # If LCIA scores are calculated, go on
            if calculate_LCIA_scores:
                
                # Loop through each characterized matrix and method to get the sum/LCIA score
                for met, characterized_matrix in characterized_matrices.items():
                    
                    # The score is simply the sum of the matrix
                    score: float = characterized_matrix.sum()
                    
                    # The ID tuple is always of length 5!
                    ID: tuple = (
                        act.key, # Key of the current activity
                        self.functional_amount, # The amount that was calculated
                        None, # Flow key, not used here
                        None, # Flow amount, not used here
                        score, # The calculated impact assessment result
                        met # The method we calculated the result for
                    ) 
                    
                    # Add to list in the result dictionary
                    self.results_raw[self.name_LCIA_scores] += [ID]
                    
                    # We add the calculated score to a temporary dict, with demand 1
                    # This because we might use it further below
                    if calculate_LCIA_scores_of_exchanges:
                        
                        # Check if activity key is already temporarily stored
                        if self._temporary_score_results.get(activity_key) is None:
                            
                            # If not, initialize new dictionary
                            self._temporary_score_results[activity_key]: dict = {}
                        
                        # Add the calculated result to it
                        self._temporary_score_results[activity_key][met]: float = (1 / self.functional_amount * score) if self.functional_amount != 0 else 0
                    
            
            # Prepare everything for the LCI and/or LCIA emission contribution
            if any((extract_LCI_emission_contribution, calculate_LCIA_emission_contribution)):                
                
                # Retrieve the emission contribution array as a dummy
                _dummy_structured_emission_array: np.array = self._get_structured_array_for_LCI_emission_contribution(database = database)
                
                # Prepare an array with the activity key of the length of the dummy emission contribution array
                emission_contribution_activity_key_array: np.array = self._get_element_array(str(activity_key), len(_dummy_structured_emission_array["activity_key"]), dtype = "U")
                
                
            # Extract the LCI emission contribution
            if extract_LCI_emission_contribution:
                
                # Extract the LCI emission contribution as the sum of the inventory matrix
                LCI_emission_contribution_array: np.array = np.array(inventory.sum(axis = 1))[:, 0]
                
                # Build or retrieve the structured emission array
                structured_array: np.array = self._get_structured_array_for_LCI_emission_contribution(database = database)
                
                # Overwrite the activity key with the current activity key
                structured_array["activity_key"]: np.array = emission_contribution_activity_key_array
                
                # Overwrite the dummy values with the contribution values
                structured_array["value"]: np.array = LCI_emission_contribution_array
                
                # We don't apply a cutoff, but remove all lines with 0 value
                structured_array_cutoff: np.array = self._apply_cut_off_to_structured_array(structured_array = structured_array, cut_off = None)
                
                # Convert structured array back to list of tuples
                structured_array_cutoff_as_list: list[tuple] = structured_array_cutoff.tolist()                       
                
                # Add to the result dictionary
                self.results_raw[self.name_LCI_emission_contributions] += structured_array_cutoff_as_list



            # Prepare everything for the LCI and/or LCIA process contribution
            if any((extract_LCI_process_contribution, calculate_LCIA_process_contribution)):                
                
                # Retrieve the process contribution array as a dummy
                _dummy_structured_process_array: np.array = self._get_structured_array_for_LCI_process_contribution(database = database)
                
                # Prepare an array with the activity key of the length of the dummy process contribution array
                process_contribution_activity_key_array: np.array = self._get_element_array(str(activity_key), len(_dummy_structured_process_array["activity_key"]), dtype = "U")
            
            
            
            # Extract the LCI process contribution
            if extract_LCI_process_contribution:
                
                # Extract the LCI process contribution as the sum of the transposed inventory matrix
                LCI_process_contribution_array: np.array = np.array(inventory.transpose().sum(axis = 1))[:, 0]
                
                # Build or retrieve the structured process array
                structured_array: np.array = self._get_structured_array_for_LCI_process_contribution(database = database)
                
                # Overwrite the activity key with the current activity key
                structured_array["activity_key"]: np.array = process_contribution_activity_key_array
                
                # Overwrite the dummy values with the contribution values
                structured_array["value"]: np.array = LCI_process_contribution_array
                
                # We don't apply a cutoff, but remove all lines with 0 value
                structured_array_cutoff: np.array = self._apply_cut_off_to_structured_array(structured_array = structured_array, cut_off = None)
                
                # Convert structured array back to list of tuples
                structured_array_cutoff_as_list: list[tuple] = structured_array_cutoff.tolist()                       
                
                # Add to the result dictionary
                self.results_raw[self.name_LCI_process_contributions] += structured_array_cutoff_as_list





            # Calculate the emission and/or process contribution
            if any((calculate_LCIA_emission_contribution, calculate_LCIA_process_contribution)):
                
                # Loop through each characterized matrix and method to get the sum/LCIA score
                for met, characterized_matrix in characterized_matrices.items():
                    
                    # Extract the LCIA emission contribution, if indicated
                    if calculate_LCIA_emission_contribution:

                        # Extract the LCIA emission contribution as the sum of the characterized matrix
                        LCIA_emission_contribution_array: np.array = np.array(characterized_matrix.sum(axis = 1))[:, 0]
                        
                        # Build or retrieve the structured emission array
                        # structured_array: np.array = self._get_structured_array_for_LCIA_emission_contribution(database = database, method = met)
                        structured_array: np.array = self._get_structured_array_for_LCIA_emission_contribution(database = database, method = met)
                        
                        # Overwrite the activity key with the current activity key
                        structured_array["activity_key"]: np.array = emission_contribution_activity_key_array
                        
                        # Overwrite the dummy values with the contribution values
                        structured_array["value"]: np.array = LCIA_emission_contribution_array
                        
                        # Apply a cutoff
                        structured_array_cutoff: np.array = self._apply_cut_off_to_structured_array(structured_array = structured_array, cut_off = self.cut_off_percentage)
                        
                        # Convert structured array back to list of tuples
                        structured_array_cutoff_as_list: list[tuple] = structured_array_cutoff.tolist()                       
                        
                        # Add to the result dictionary
                        self.results_raw[self.name_LCIA_emission_contributions] += structured_array_cutoff_as_list
                        
                        


                    # Extract the LCIA process contribution, if indicated
                    if calculate_LCIA_process_contribution:
                        
                        # Extract the LCIA process contribution as the sum of the transposed characterized matrix
                        LCIA_process_contribution_array: np.array = np.array(characterized_matrix.transpose().sum(axis = 1))[:, 0]
                        
                        # Build or retrieve the structured process array
                        structured_array: np.array = self._get_structured_array_for_LCIA_process_contribution(database = database, method = met)
                        
                        # Overwrite the activity key with the current activity key
                        structured_array["activity_key"]: np.array = process_contribution_activity_key_array
                        
                        # Overwrite the dummy values with the contribution values
                        structured_array["value"]: np.array = LCIA_process_contribution_array
                        
                        # Apply a cutoff
                        structured_array_cutoff: np.array = self._apply_cut_off_to_structured_array(structured_array = structured_array, cut_off = self.cut_off_percentage)
                        
                        # Convert structured array back to list of tuples
                        structured_array_cutoff_as_list: list[tuple] = structured_array_cutoff.tolist()                       
                        
                        # Add to the result dictionary
                        self.results_raw[self.name_LCIA_process_contributions] += structured_array_cutoff_as_list
 
                        
        # Print summary statement(s)
        if self.progress_bar:
            
            # Save current time
            end_round_1: datetime.datetime = datetime.datetime.now()
            
            # Print statement
            print("  - Calculation time: {}".format(self.convert_timedelta(end_round_1 - start_round_1)))
            
            if calculate_LCIA_scores:
                print("      - {} LCIA score(s) from {} activity/ies & {} methods were calculated".format(len(self.activities)*len(self.methods), len(self.activities), len(self.methods)))
        
        # In case we want to calculate the scores of the exchanges, we need to go again through all exchanges and do the calculation
        if calculate_LCIA_scores_of_exchanges:
            
            # Check if progress bar should be printed
            if self.progress_bar:
                
                # Wrap progressbar around iterables
                iterables: list[tuple] = hp.progressbar(self.results_raw[self.name_LCI_exchanges], prefix = "\nCalculate LCIA scores of exchanges ...")
                
            else:
                # Otherwise, simply create iterable variable
                iterables: list[tuple] = self.results_raw[self.name_LCI_exchanges]
            
            # To calculate the LCIA scores for exchanges, we need to preload the characterization factors
            # This is a sacrification, BUT it will bring much more value if there are many exchanges to be calculated because we can omit the try, except statement (LCA calculation) if we already identify biosphere flows early
            for met in self.methods:
                self._load_characterization_factors(method = met)
            
            # Loop through all activities
            for (act_key, act_amount, flow_key, flow_amount, _, _) in iterables:
                                
                # Initialize a list to potentially store all methods for which calculation was unsuccessful
                methods_for_which_no_scores_were_calculated: list[tuple] = []
                
                # Go again through all methods
                for met in self.methods:
                                        
                    # Check if the score has already been calculated
                    if self._temporary_score_results.get(flow_key, {}).get(met) is not None:
                        
                        # Construct and add tuple to raw results
                        self.results_raw[self.name_LCIA_immediate_scores] += [(act_key,
                                                                               act_amount,
                                                                               flow_key,
                                                                               flow_amount,
                                                                               flow_amount * self._temporary_score_results[flow_key][met],
                                                                               met
                                                                               )]
                        # Go to next
                        continue
                    
                    # Retrieve characterization factor, if possible 
                    cf: (float | None) = self.characterization_factors[met].get(flow_key)                    
                    
                    # If successful, the current flow is of type biosphere and we can simply multiply the cf with the flow amount and go on
                    if cf is not None:
                        
                        # Construct and add tuple to raw results
                        self.results_raw[self.name_LCIA_immediate_scores] += [(act_key,
                                                                               act_amount,
                                                                               flow_key,
                                                                               flow_amount,
                                                                               flow_amount * cf,
                                                                               met
                                                                               )]
                        # Go to next
                        continue
                    
                    # Add to list
                    methods_for_which_no_scores_were_calculated += [met]

                
                # If everything has already been successfully calculated, go to next activity
                if methods_for_which_no_scores_were_calculated == []:
                    continue
                
                # If we arrive here, we need to run through the matrix calculation
                # First get the database the activity belongs to
                database: str = act_key[0]

                # Get the BW object,
                try:
                    # We try to construct the LCA object
                    lca_object: bw2calc.lca.LCA = self._get_LCA_object(database = database)
                    
                    # and to redo the inventory matrix (which takes quite some time)
                    lca_object.redo_lci({flow_key: flow_amount})
                
                except OutsideTechnosphere:
                    # If we fail to redo the lca because the key is outside of the technosphere, that means that the current flow belongs to a biopshere database
                    # Since we already tried to do a simple cf calculation (see above), it means that the current flow is not characterized in the specific methods
                    # We can simply add a 0 now
                    self.results_raw[self.name_LCIA_immediate_scores] += [(act_key,
                                                                           act_amount,
                                                                           flow_key,
                                                                           flow_amount,
                                                                           float(0),
                                                                           m
                                                                           ) for m in methods_for_which_no_scores_were_calculated]
                    # We go on
                    continue
                
                
                # We then extract the inventory matrix
                inventory: np.matrix = lca_object.inventory
                
                # Loop through each method and create the characterized matrices by multiplying the inventory matrix with the 
                for met in methods_for_which_no_scores_were_calculated:
                    
                    # Build or simply get the matrix
                    matrix = self._get_characterization_matrix(database = database, method = met)
                    
                    # Multiply the matrices
                    characterized_matrix = (matrix * inventory)
                    
                    # The score is simply the sum of the matrix
                    score: float = characterized_matrix.sum()
                
                    # Construct and add tuple to raw results
                    self.results_raw[self.name_LCIA_immediate_scores] += [(act_key,
                                                                           act_amount,
                                                                           flow_key,
                                                                           flow_amount,
                                                                           score,
                                                                           met
                                                                           )]

            
    
    def get_characterization_factors(self, methods: (list[tuple] | None) = None, extended: bool = True) -> list[dict]:
        
        # If no methods are specified, the ones specified in the calculation class will be exported
        if methods is None:
            methods: list[tuple] = self.methods
        
        else:
            # Extract all methods that are not registered in the Brightway background
            check_methods = [str(m) for m in methods if m not in bw2data.methods]
            
            # Check if all methods are registered in the Brightway background
            if check_methods != []:
                raise ValueError("They following methods are not registered:\n - " + "\n - ".join(check_methods))
            
        
        # Initialize a new list to store the characterization factors to
        characterization_factors: list[dict] = []
        
        # Loop through each method individually
        for method in methods:
            
            # Load characterization factors, if not yet loaded
            self._load_characterization_factors(method = method)
            
            # Loop through each CF individually
            for (database, code), cf in self.characterization_factors[method].items():
                
                # Check if flows should extensively be described
                if not extended:
                    cf_as_dict: dict = {self.k_flow_database: database,
                                        self.k_flow_code: code,
                                        self._cf_k_name: cf,
                                        self._method_k_name: method}
                    
                else:
                    # Retrieve the specified dictionary values from the Brightway background activities
                    flow_as_dict: dict = self._get_act_as_dict((database, code), self.keys_to_extract_from_BW_acts)
                    method_unit: dict = {self._name_sep.join((self._method_k_name, "unit")): self._get_method_unit(method = method)}
                    
                    # Construct dictionary
                    cf_as_dict: dict = {self.k_flow_database: database,
                                        self.k_flow_code: code,
                                        **{(self._name_sep.join((self._flow_k_name, k))): v for k, v in flow_as_dict.items()},
                                        self._cf_k_name: cf,
                                        self._method_k_name: method,
                                        **method_unit}
                
                # Add characterization dictionary to the list
                characterization_factors += [{k: v for k, v in cf_as_dict.items() if v is not None}]
        
        # Return the list
        return characterization_factors
                
    
    
    def get_results(self, extended: bool = True) -> list[dict]:
        
        # Check if results dictionary is available        
        if not hasattr(self, "results_raw"):
            raise ValueError("Nothing has been calculated yet. Use .calculate() to run calculation first.")
        
        # Initialize a new results dictionary to where results will be stored
        if extended:
            self.results_extended: dict = {k: [] for k in list(self.results_raw.keys()).copy()}
        else:
            self.results_simple: dict = {k: [] for k in list(self.results_raw.keys()).copy()}
        
        # Print statement
        print("\n-----")
        print("Processing results...") if not extended else print("Processing results, incl. retrieving of activity meta data")
        
        # Loop through the results individually
        for result_type, results in self.results_raw.items():
            
            # # Check if progress bar should be printed to console
            # if self.progress_bar:
                
            #     # Wrap progress bar around iterator
            #     results: list[tuple] = hp.progressbar(results, prefix = "\nPreparing '{}' results ...".format(result_type))
            
            # Loop through each result item
            for (act_key, act_amount, flow_key, flow_amount, score, method) in results:  
                
                # If everything is 0, we can go to the next one and do not need to add it to the results
                if act_amount == 0 and flow_amount == 0 and score == 0:
                    continue
                
                # In certain cases, tuples have been written as strings
                # We need to revert this by using ast
                # ... revert activity key tuple
                if isinstance(act_key, str):
                    act_key: tuple[str, str] = ast.literal_eval(act_key)
                
                # ... revert flow key tuple
                if isinstance(flow_key, str):
                    flow_key: tuple[str, str] = ast.literal_eval(flow_key)
                
                # ... revert method tuple
                if isinstance(method, str):
                    method: tuple[str, str] = ast.literal_eval(method)
                
                # Retrieve individual variables, for simplified handling
                v_act_database: (str | None) = act_key[0] if act_key is not None else None
                v_act_code: (str | None) = act_key[1] if act_key is not None else None
                v_flow_database: (str | None) = flow_key[0] if flow_key is not None else None
                v_flow_code: (str | None) = flow_key[1] if flow_key is not None else None
                
                # Check if flows should be described extensively
                if not extended:
                    result_as_dict: dict = {self.k_act_database: v_act_database,
                                            self.k_act_code: v_act_code,
                                            self.k_act_amount: act_amount,
                                            self.k_flow_database: v_flow_database,
                                            self.k_flow_code: self.rest_name if flow_key == self.rest_key else v_flow_code,
                                            self.k_flow_amount: flow_amount,
                                            self._score_k_name: score,
                                            self._method_k_name: method}
                    
                    # Add the constructed dictionary to the list
                    self.results_simple[result_type] += [{k: v for k, v in result_as_dict.items() if v is not None}]
        
                    
                else:
                    # Retrieve the specified dictionary values from the Brightway background activities
                    act_as_dict: dict = self._get_act_as_dict(act_key, self.keys_to_extract_from_BW_acts) if act_key is not None else {}
                    flow_as_dict: dict = self._get_act_as_dict(flow_key, self.keys_to_extract_from_BW_acts) if flow_key and flow_key != self.rest_key is not None else {}
                    method_unit: dict = {self._name_sep.join((self._method_k_name, "unit")): self._get_method_unit(method = method)} if method is not None else {}
                    
                    # Construct dictionary
                    result_as_dict: dict = {self.k_act_database: v_act_database,
                                            self.k_act_code: v_act_code,
                                            **{(self._name_sep.join((self._act_k_name, k))): v for k, v in act_as_dict.items()},
                                            self.k_act_amount: act_amount,
                                            self.k_flow_database: v_flow_database,
                                            self.k_flow_code: self.rest_name if flow_key == self.rest_key else v_flow_code,
                                            **{(self._name_sep.join((self._flow_k_name, k))): v for k, v in flow_as_dict.items()},
                                            self.k_flow_amount: flow_amount,
                                            self._score_k_name: score,
                                            self._method_k_name: method,
                                            **method_unit}
                
                    # Add the constructed dictionary to the list
                    self.results_extended[result_type] += [{k: v for k, v in result_as_dict.items() if v is not None}]
        
        # Print statement
        print("Completed")
        
        # Return
        if extended:
            
            # Return extended results
            return self.results_extended
        
        else:
            # Return simple results
            return self.results_simple

    


    # Function to export the results to XLSX/CSV
    def write_results(self,
                      path: (pathlib.Path | str | None),
                      filename: (str | None) = None,
                      use_timestamp_in_filename: bool = True,
                      extended: bool = True) -> None:
        
        # Check if extended results have already been prepared and are available
        if (extended and not hasattr(self, "results_extended")) or (not extended and not hasattr(self, "results_simple")):

            # If not, prepare them first
            _results_: dict[str, list[dict]] = self.get_results(extended = extended)
            
            # Delete the results variable to keep memory minimal
            del _results_
        
        # Select results
        results_to_write: dict = self.results_extended if extended else self.results_simple
                
        # Convert results to dataframe
        results_df: dict[str, pd.DataFrame] = {k: pd.DataFrame(v) for k, v in results_to_write.items()}

        # Create a path if not provided by the function
        # If not provided, the local Brightway2 folder will be used to save results
        if path is None:
            path: pathlib.Path = pathlib.Path(bw2data.projects.output_dir)
        
        # If path is of type string, provide as pathlib path
        elif isinstance(path, str):
            path: pathlib.Path = pathlib.Path(path)
            
        # Check if the path exists
        if not path.is_dir():
            raise ValueError("Path '" + str(path) + "' does not exist")
            
        # Extract current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Create filename if not provided
        if filename is None:
            
            # Either use or do not use the timestamp in the filename
            # depending on how specified in the function input
            if use_timestamp_in_filename:
                
                # Give file name
                filename = current_time + "_LCA"
                
            else:
                # Give file name
                filename = "LCA"
        
        else:
            # The same as above
            if use_timestamp_in_filename:
                
                # Give file name
                filename = current_time + "_" + filename
        
        # Initialize a documentation variable
        documentation = {self.name_LCIA_scores: """This dataframe contains the result of the LCA calculation
                         and shows the total environmental impact of all activities (LCI) and methods (LCIA) combinations""",
                         
                         self.name_LCI_exchanges: """This dataframe contains detailed information about the inventories.
                         It shows the biosphere emissions and technosphere activities contributing to an activity (LCI).""",
                         
                         # !!! DO THE DOCUMENTATIONS HERE
                         self.name_LCI_emission_contributions: """ TODO """,
                         
                         # !!! DO THE DOCUMENTATIONS HERE
                         self.name_LCI_process_contributions: """ TODO """,
                         
                         # !!! DO THE DOCUMENTATIONS HERE
                         self.name_LCIA_immediate_scores: """ TODO """,
                         
                         # !!! DO THE DOCUMENTATIONS HERE
                         self.name_LCIA_emission_contributions: """ TODO """,
                         
                         # !!! DO THE DOCUMENTATIONS HERE
                         self.name_LCIA_process_contributions: """ TODO """,

                         }
        
        # Write data to XLSX
        # Initialise the writer variable
        writer = pd.ExcelWriter(path / (str(filename) + ".xlsx"))
        
        # Convert the documentation dictionary into a dataframe
        documentation_df: pd.DataFrame = pd.DataFrame([{"Sheet": k, "Description": v} for k, v in documentation.items() if k in results_df])
        
        # Add the documentation dataframe to the writer
        documentation_df.to_excel(writer, sheet_name = "Documentation")
        
        # Add each result dataframe to the writer
        for df_name, df in results_df.items():
            
            # Check if the length of the dataframe exceeds a million and more rows
            # If not, we are good to go with writing an excel file
            if len(df) < 1048000:
                
                # We simply append the result dataframe to the excel workbook
                df.to_excel(writer, sheet_name = df_name[:30])
                
            else:
                # If there are more than one million rows, we can not add the results in a new sheet.
                # In that case, we write a standalone csv
                df.to_csv((path / str(df_name + ".csv")))

        # Save the XLSX
        writer.close()
        
        # Print filepath if specified
        if self.progress_bar:
            
            # Print statement saying where XLSX file was stored
            print("\n-----\nLCA results saved to the following path:\n" + str(path))




    # Function to convert time delta in a readable, nice string
    def convert_timedelta(self, timedelta: datetime.timedelta) -> str:
        
        # Check function input type
        hp.check_function_input_type(self.convert_timedelta, locals())
        
        # Get total days and total seconds
        days, seconds = timedelta.days, timedelta.seconds
        
        # Convert to hours, minutes and seconds
        hours = days * 24 + seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = (seconds % 60)
        
        # Create string
        if hours > 0:
            string: str = str(hours) + " hour(s) and " + str(minutes) + " minute(s)"
            
        elif minutes > 0:
            string: str = str(minutes) + " minute(s) and " + str(seconds) + " second(s)"
            
        elif seconds > 0:
            string: str = str(seconds) + " second(s)"
            
        else:
            string: str = "less than a second"
            
        # Return string
        return string
    
    


#%%

# if __name__ == "__main__":
    
#     here: pathlib.Path = pathlib.Path(__file__).parent
    
#     def change_brightway_project_directory(BRIGHTWAY2_DIR: (pathlib.Path | str),
#                                            verbose: bool = True):
        
#         # Make variable check
#         hp.check_function_input_type(change_brightway_project_directory, locals())
        
#         # Print statement
#         if verbose:
#             print("BRIGHTWAY2_DIR is set to the following path:\n" + str(BRIGHTWAY2_DIR) + "\n")
        
#         # Those lines are directly taken from Brightway
#         # It constructs some fields new and sets the path according to the one given by ourselves
#         bw2data.projects._base_data_dir = str(BRIGHTWAY2_DIR)
#         bw2data.projects._base_logs_dir = os.path.join(str(BRIGHTWAY2_DIR), "logs")
#         bw2data.projects.db = bw2data.sqlite.SubstitutableDatabase(os.path.join(str(BRIGHTWAY2_DIR), "projects.db"), [bw2data.project.ProjectDataset])
#         bw2data.projects.set_current("default", update = False)
    
#     change_brightway_project_directory(str(here / "Brightway2_projects"))
#     project_name: str = "Food databases"
#     bw2data.projects.set_current(project_name)
    
#     acts: list = [m for m in bw2data.Database("AgriFootprint v6.3 - SimaPro")]
#     mets: list[tuple] = [m for m in bw2data.methods][0]
    
#     lca_calculation: LCACalculation = LCACalculation(activities = acts,
#                                                        methods = mets,
#                                                        functional_amount = 1,
#                                                        cut_off_percentage = None,
#                                                        exchange_level = 1)
    
#     lca_calculation.calculate(calculate_LCIA_scores = False,
#                               extract_LCI_exchanges = False,
#                               extract_LCI_emission_contribution = False,
#                               extract_LCI_process_contribution = True,
#                               calculate_LCIA_scores_of_exchanges = False,
#                               calculate_LCIA_emission_contribution = False,
#                               calculate_LCIA_process_contribution = False)
    
#     contribution_results = lca_calculation.get_results(extended = True)
        


