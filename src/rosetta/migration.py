"""Migrations: replace fields (and scale amounts) of activities and exchanges based on a mapping.

A migration is defined by a list of ``fields`` that identify the item to migrate (FROM) and, for each FROM,
one or more target field values (TO) with a multiplier. It can be read from an Excel file (columns ``FROM_<field>``,
``TO_<field>`` and an optional ``multiplier`` column) or from a JSON file with the keys 'fields' and 'data'.

    migration = Migration.from_excel("custom_migration.xlsx")
    importer.migrate(migration)
"""

import ast
import copy
import json
import pathlib
from typing import Self

import pandas as pd

from . import _helpers as hp


def create_structured_migration_dictionary_from_excel(excel_dataframe: pd.DataFrame) -> dict[str, list[tuple] | dict[tuple, list[dict]]]:
    
    # Check function input type
    hp.check_function_input_type(create_structured_migration_dictionary_from_excel, locals())
    
    # Fill NaN values with empty string
    df: pd.DataFrame = excel_dataframe.replace({float("NaN"): None})
    
    # Extract columns
    cols: list[str] = [str(m) for m in list(df.columns)]
    
    # Separate FROM and TO columns
    FROM_cols: list[str] = [m for m in cols if "FROM_" in m]
    TO_cols: list[str] = [m for m in cols if "TO_" in m]
    multiplier_cols: list[str] = [m for m in cols if "multiplier" in m.strip().lower()]
    multiplier_col: (str | None) = multiplier_cols[0] if len(multiplier_cols) > 0 else None
    
    # We need information for all FROM cols. Otherwise, the excel is invalid
    if any([[n for n in list(df[m]) if n is None] != [] for m in FROM_cols]):
        raise ValueError("Invalid migration Excel. Some of the FROM columns contain empty values.")
    
    # Create fields --> all names from the FROM columns
    fields: list[str] = [m.replace("FROM_", "") for m in FROM_cols]
    
    # Initialize a list for the 'data'
    _data: dict = {}
    
    # Loop through each row in the dataframe
    for idx, row in df.iterrows():
        
        # Extract the FROM and the multiplier of the current line
        FROM: tuple = tuple([row[m] for m in FROM_cols])
        multiplier: float = row[multiplier_col] if multiplier_col is not None and row.get(multiplier_col) is not None else float(1)
        
        # Initialize new object in dictionary for the FROM, if not yet existing
        if FROM not in _data:
            _data[FROM]: list = []
        
        # Extract the TO as a dictionary
        TO: dict = {(m.replace("TO_", "")): row[m] for m in TO_cols if row[m] is not None}

        # Add the tuple to the list
        _data[FROM] += [(TO, multiplier)]

    return {"fields": fields, "data": [(FROM, TOs) for FROM, TOs in _data.items()]}


def create_migration_mapping(json_dict: dict):
    
    # Check function input type
    hp.check_function_input_type(create_migration_mapping, locals())
    
    # Raise error if format is wrong
    if "data" not in json_dict or "fields" not in json_dict:
        raise ValueError("Invalid migration dictionary. 'data' and 'fields' need to be provided.")
    
    # 'data' needs to be a dict
    if not isinstance(json_dict["data"], list): 
        raise ValueError("Invalid migration dictionary. 'data' needs to be a list containing tuples.") 
    
    # More specifically, 'data' needs to be a list with tuples or list of length 2. The first one is the FROM, the second one TO
    if not all([True if isinstance(m, list | tuple) and isinstance(n, list | tuple) else False for m, n in json_dict["data"]]):
        raise ValueError("Invalid migration dictionary. 'data' needs to be a list or a tuple consisting of elements that are again lists or tuples of length 2.")
    
    # 'fields' needs to be a list or a tuple
    if not isinstance(json_dict["fields"], list | tuple):
        raise ValueError("Invalid migration dictionary. 'fields' needs to be a list or a tuple.")
    
    # 'fields' needs to be a list of strings
    if not all([isinstance(m, str) for m in json_dict["fields"]]):
        raise ValueError("Invalid migration dictionary. 'fields' needs to be a list or tuple of strings.")
         
    # Initialize mapping dictionary
    mapping: dict = {}

    # Construct mapping dictionary. Looping through all elements
    for FROM_orig, TOs in json_dict["data"]:
        
        # First, we need to adapt the FROMs and the TOs
        # We use ast literal to evaluate the elements and merge them to the corresponding Python type
        # We also check for lists and replace them with the immutable tuple types
        
        # Initialize new variables
        FROM_tuple: tuple = ()
        TO_dicts: dict = {}
        
        if isinstance(FROM_orig, list | tuple):
            
            # Loop through each element from the FROM list
            for x in FROM_orig:
                
                # Evaluate, if possible. Otherwise, use the value as it is right now
                try: xx = ast.literal_eval(x)
                except: xx = x
                
                # Convert list to tuples
                if isinstance(xx, list):
                    xx = tuple(xx)
                
                # Append to variable
                FROM_tuple += (xx,)
         
        elif isinstance(FROM_orig, str):
             FROM_tuple: tuple = ast.literal_eval(FROM_orig)
             
        else:
            raise ValueError("Did not catch the key {} with type {} when creating the migration mapping.".format(FROM_orig, type(FROM_orig).__name__))
         
        # Check if FROM_tuple already exists in the mapping dictionary. This should not be the case.
        if FROM_tuple in mapping:
            raise ValueError("FROM_tuple has already been introduced in the mapping and should not be introduced again considering that the migration dictionary is of consistent nature.")
        
        # Initialize new list to append to
        mapping[FROM_tuple]: list = []
        
        # Loop through each TO element to map to
        for TO_orig, multiplier in TOs:
            
            # Initialize new dictionary
            TO_dict: dict = {}
        
            # Loop through each key/value pair of the TO element
            for y, z in TO_orig.items():
                
                # Evaluate, if possible. Otherwise, use the value as it is right now
                try: yy = ast.literal_eval(y)
                except: yy = y
                
                # Evaluate, if possible. Otherwise, use the value as it is right now
                try: zz = ast.literal_eval(z)
                except: zz = z
                
                # Convert list to tuples
                if isinstance(yy, list):
                    yy = tuple(yy)
                    
                # Convert list to tuples
                if isinstance(zz, list):
                    zz = tuple(zz)
                
                # Append to variable
                TO_dict[yy] = zz
                
            # Append dictionary to existing list
            mapping[FROM_tuple] += [(TO_dict, multiplier)]
        
    return tuple(json_dict["fields"]), mapping


def apply_migration_mapping(db_var,
                            fields: tuple,
                            migration_mapping: dict,
                            migrate_activities: bool,
                            migrate_exchanges: bool):
    
    # Check function input type
    hp.check_function_input_type(apply_migration_mapping, locals())
    
    # Amount fields to which the 'multiplier' should be applied to
    amount_fields_ds: list[str] = ["production amount", "output amount"]
    amount_fields_exc: list[str] = ["amount", "loc", "scale", "shape", "minimum", "maximum"]
    
    # Migration counter
    n_ds: int = 0
    n_exc: int = 0
    
    # Migration duplicate checker
    dup_ds: dict = {}
    dup_exc: dict = {}
    
    # Create new list to be returned afterwards
    new_db_var: list[dict] = []
    
    # Loop through each element in the current database data (inventory)
    for ds in db_var:
        
        # Initialize a new list object to store exchanges to
        new_exchanges: list = []
        
        # We do the same as above also for the exchanges
        # Loop through each exchange of the current inventory
        for exc in ds["exchanges"]:
            
            # Check if exchanges should be migrated
            if migrate_exchanges:
            
                # We try to find a suitable entry of the migration mapping for the current exchange
                # If possible, we replace the values of the current exchange with the ones from the migration mapping

                # We first extract the respective information of the fields of the current exchange with which we search in the migration mapping
                exc_ID: tuple = tuple([exc[m] for m in fields if m in exc])
                
                # We check if we find a corresponding item in the migration mapping
                map_tos: (tuple[dict, float] | None) = migration_mapping.get(exc_ID)
                    
                # Go on only if a mappable has been found
                if map_tos is not None:
                    
                    # Loop through each mappable item
                    for map_to in map_tos:
                    
                        # Deepcopy the existing exchange
                        exc_copied: dict = copy.deepcopy(exc)    
                    
                        # We loop through each key/value pair
                        for exc_k_new, exc_v_new in map_to[0].items():
                            
                            # We replace (or add if not existing) the values of the keys in the exchange
                            exc_copied[exc_k_new] = exc_v_new
                        
                        # We loop through all the amount fields (specified above) individually and add the multiplier
                        for amount_field_exc in amount_fields_exc:
                            
                            # If it exists in the current dictionary, we update the field
                            # We multiply the current value with the multiplier value
                            if amount_field_exc in exc_copied:
                                exc_copied[amount_field_exc] *= map_to[1]
                                
                        # We need to update the negative key
                        if "negative" in exc_copied:
                            exc_copied["negative"] = exc_copied["amount"] < 0
                        
                        # Add new exchange to list
                        new_exchanges += [exc_copied]
                        
                    # Increase counter
                    if dup_exc.get(exc_ID) is None:
                        n_exc += 1
                        dup_exc[exc_ID]: bool = True
                
                else:
                    # Simply add the already existing exchange without any modification to the new list
                    new_exchanges += [exc]
                
            else:
                # Simply add the already existing exchange without any modification to the new list
                new_exchanges += [exc]
        
        
        
        # Check if activities should be migrated
        if migrate_activities:
        
            # We try to find a suitable entry of the migration mapping for the current inventory
            # If possible, we replace the values of the current inventory with the ones from the migration mapping
                
            # We first extract the respective information of the fields of the current inventory with which we search in the migration mapping
            ds_ID: tuple = tuple([ds[m] for m in fields if m in ds])
            
            # We check if we find a corresponding list in the migration mapping
            map_tos: (tuple[dict, float] | None) = migration_mapping.get(ds_ID)
            
            # We can only go on, if a mapping has been found
            if map_tos is not None:
                
                # Loop through each mappable item
                for map_to in map_tos:
                    
                    # Deepcopy the existing activity
                    ds_copied: dict = copy.deepcopy(ds) 
                
                    # We loop through each key/value pair
                    for ds_k_new, ds_v_new in map_to[0].items():
                        
                        # We replace (or add if not existing) the values of the keys in the exchange
                        ds_copied[ds_k_new] = ds_v_new
                        
                    # We loop through all the amount fields (specified above) individually and add the multiplier
                    for amount_field_ds in amount_fields_ds:
                        
                        # If it exists in the current dictionary, we update the field
                        # We multiply the current value with the multiplier value
                        if amount_field_ds in ds_copied:
                            ds_copied[amount_field_ds] *= map_to[1]
                    
                    # Add the copied activity with the modifications together with the new list of exchanges to the new database list
                    new_db_var += [{**ds_copied,
                                    "exchanges": new_exchanges}]
                    
                # Increase counter
                if dup_ds.get(ds_ID) is None:
                    n_ds += 1
                    dup_ds[ds_ID]: bool = True
                    
                
            else:
                # Simply add the already existing activity with the new list of exchanges to the new database list
                new_db_var += [{**ds,
                                "exchanges": new_exchanges}]
        
        else:
            # Simply add the already existing activity with the new list of exchanges to the new database list
            new_db_var += [{**ds,
                            "exchanges": new_exchanges}]
    
    # Print the amount of migrated ds and exc
    print("Migrated {} unique inventories and {} unique exchanges".format(n_ds, n_exc))
            
    return new_db_var


class Migration:
    """A migration mapping that can be applied to a list of datasets.

    Parameters
    ----------
    fields
        Fields that identify an activity or exchange to migrate, e.g. ``("name", "unit", "location")``.
    mapping
        ``{FROM_tuple: [(TO_dict, multiplier), ...]}``, where ``FROM_tuple`` holds the values of ``fields``.
    """

    def __init__(self, fields: tuple[str, ...], mapping: dict[tuple, list[tuple[dict, float]]]) -> None:
        self.fields: tuple[str, ...] = tuple(fields)
        self.mapping: dict[tuple, list[tuple[dict, float]]] = mapping

    @classmethod
    def from_dict(cls, structured: dict) -> Self:
        """Create from a structured dictionary ``{"fields": [...], "data": [(FROM, [(TO, multiplier), ...]), ...]}``."""
        fields, mapping = create_migration_mapping(json_dict=structured)
        return cls(fields, mapping)

    @classmethod
    def from_json(cls, filepath: pathlib.Path | str) -> Self:
        with open(filepath) as file:
            return cls.from_dict(json.load(file))

    @classmethod
    def from_excel(cls, filepath: pathlib.Path | str) -> Self:
        excel: pd.DataFrame = pd.read_excel(filepath)
        return cls.from_dict(create_structured_migration_dictionary_from_excel(excel_dataframe=excel))

    @classmethod
    def from_file(cls, filepath: pathlib.Path | str) -> Self:
        """Create from an Excel (.xlsx/.xls) or JSON (.json) file, depending on the file extension."""
        suffix: str = pathlib.Path(filepath).suffix.lower()
        if suffix == ".json":
            return cls.from_json(filepath)
        if suffix in (".xlsx", ".xls", ".xlsm"):
            return cls.from_excel(filepath)
        raise ValueError("Unsupported migration file type '{}'. Use an Excel or JSON file.".format(suffix))

    def apply(self, data: list[dict], activities: bool = False, exchanges: bool = True) -> list[dict]:
        """Apply the migration to ``data`` and return the migrated list of datasets."""
        return apply_migration_mapping(db_var=data,
                                       fields=self.fields,
                                       migration_mapping=self.mapping,
                                       migrate_activities=activities,
                                       migrate_exchanges=exchanges)

    def __len__(self) -> int:
        return len(self.mapping)

    def __repr__(self) -> str:
        return "{}(fields={}, entries={})".format(type(self).__name__, self.fields, len(self))
