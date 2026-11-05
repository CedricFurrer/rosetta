import re
import pathlib
import pandas as pd
from bw2io.units import normalize_units as normalize_units_function
here: pathlib.Path = pathlib.Path(__file__).parent



class Correspondence():
    
    def __init__(self,
                 ecoinvent_model_type: str) -> None:
        
        self.FROM_definer: str = "FROM"
        self.TO_definer: str = "TO"
        self.whitespace_replacer: str = "_"
        self.version_replacer: str = "."
        
        self.ecoinvent_model_type: str = ecoinvent_model_type
        self.ecoinvent_model_type_cutoff: str = "cutoff"
        self.ecoinvent_model_type_apos: str = "apos"
        self.ecoinvent_model_type_consequential: str = "consequential"
        self.allowed_ecoinvent_model_types: list[str] = [self.ecoinvent_model_type_cutoff, self.ecoinvent_model_type_apos, self.ecoinvent_model_type_consequential]
        
        self.key_name_version: str = "version"
        self.key_name_version_uppered: str = self.key_name_version[0].upper() + self.key_name_version[1:].lower()
        self.key_name_FROM_version: str = self.whitespace_replacer.join((self.FROM_definer, self.key_name_version))
        self.key_name_TO_version: str = self.whitespace_replacer.join((self.TO_definer, self.key_name_version))
        self.key_name_activity_uuid: str = "activity_uuid"
        self.key_name_reference_product_uuid: str = "reference_product_uuid"
        self.key_name_activity_name: str = "activity_name"
        self.key_name_reference_product_name: str = "reference_product_name"
        self.key_name_location_name: str = "location"
        self.key_name_unit_name: str = "unit"
        self.key_name_multiplier: str = "multiplier"
        self.key_name_multiplier_uppered: str = self.key_name_multiplier[0].upper() + self.key_name_multiplier[1:].lower()
        self.key_name_multiplier_uppered_plural: str = self.key_name_multiplier_uppered + "s"
        
        self.raw_data: dict = {}
        self.df_interlinked_data_raw: dict = {}
        self.interlinked_data: dict = {}
        self.check_multipliers: dict = {}
        
        self.identifier_1: tuple[str, str] = tuple([self.key_name_activity_uuid, self.key_name_reference_product_uuid])
        self.identifier_2: tuple[str, str, str, str] = tuple([self.key_name_activity_name, self.key_name_reference_product_name, self.key_name_location_name, self.key_name_unit_name])
        self.identifier_1_uppered: tuple[str, str] = tuple([m[0].upper() + m[1:].lower() for m in self.identifier_1])
        self.identifier_2_uppered: tuple[str, str, str, str] = tuple([m[0].upper() + m[1:].lower() for m in self.identifier_2])
        self.FROM_identifier_1: tuple[str, str] = tuple([self.whitespace_replacer.join((self.FROM_definer, m)) for m in self.identifier_1])
        self.FROM_identifier_2: tuple[str, str] = tuple([self.whitespace_replacer.join((self.FROM_definer, m)) for m in self.identifier_2])
        self.TO_identifier_1: tuple[str, str] = tuple([self.whitespace_replacer.join((self.TO_definer, m)) for m in self.identifier_1])
        self.TO_identifier_2: tuple[str, str] = tuple([self.whitespace_replacer.join((self.TO_definer, m)) for m in self.identifier_2])


        # Raise error, if model type is None of the defaults
        if ecoinvent_model_type not in self.allowed_ecoinvent_model_types:
            raise ValueError("Current model type '{}' is not allowed. Use one of the following: {}".format(self.ecoinvent_model_type, self.allowed_ecoinvent_model_types))
        
        
        
    def read_correspondence_dataframe(self,
                                      filepath_correspondence_excel: pathlib.Path,
                                      FROM_version: tuple[int, int],
                                      TO_version: tuple[int, int],
                                      ) -> None:
        
        # Names of sheets in the excel file depending on the ecoinvent model type
        sheet_name_mapping: dict = {self.ecoinvent_model_type_cutoff: ["Cut-off", "Cut-Off", "cut-off", "cutoff"],
                                    self.ecoinvent_model_type_apos: ["apos", "APOS"],
                                    self.ecoinvent_model_type_consequential: ["consequential", "Consequential", "conseq"]}

        # Sheet names to search for in the excel files
        sheetnames: list[str] = sheet_name_mapping[self.ecoinvent_model_type]

        # Relevant columns in the excel files
        actID_cols: list[str] = ["activityID", "Activity UUID"]
        prodID_cols: list[str] = ["Product UUID"]
        ref_cols: list[str] = ["product name", "Product Name"]
        act_cols: list[str] = ["activityName", "Activity Name"]
        loc_cols: list[str] = ["geography", "Geography"]
        unit_cols: list[str] = ["unit", "Unit"]
        mult_cols: list[str] = ["amount of the replacement", "Replacement amount", "replacement amount", "replacement share"]
    
        # Make a version string, based on the version tuple from the element
        FROM_version_str: str = self.version_replacer.join([str(m) for m in FROM_version])
        TO_version_str: str = self.version_replacer.join([str(m) for m in TO_version])
        
        # Print statement
        print("Reading", FROM_version, " -> ", TO_version)
        
        # Read the correspondence excel file for the current versions
        excel: dict[pd.DataFrame] = pd.read_excel(filepath_correspondence_excel, sheet_name = None)
        
        # Only use the sheet that we want to use --> either cut-off, apos or consequential
        # Because the files use different names for the systems, we need to search for the appropriate one
        sheet: list[str] = [m for m in sheetnames if m in excel]
        
        # If we could not identify the excel sheet for the current system, we raise an error
        assert len(sheet) == 1, "None or more than one sheet name ({}) matches in the excel ({})".format(sheet, filepath_correspondence_excel)
        
        # The raw data to use
        df_orig: pd.DataFrame = excel[sheet[0]]
        
        # We need to adjust the header
        # We need to skip the first rows. First, we identify where the header is located
        # We can find the header, as the first line, where no NaN values are found.
        # We add a column to the dataframe. Each row is checked whether any value in that row is NaN. If yes, it is True, otherwise it is False.
        df_orig["_header_selection"] = df_orig.isnull().any(axis = 1)
        
        # We locate the header as the first row, where all values are not empty (NaN)
        new_header_idx: int = [idx for idx, m in df_orig.iterrows() if not m["_header_selection"]][0]
        
        # We extract the new header based on the location found beforehand
        new_header_orig: list[str] = list(df_orig.loc[new_header_idx])
        
        # We identify the duplicated headers
        doubles: list[str] = [m for m in new_header_orig if new_header_orig.count(m) > 1]
        
        # Initialize new lists
        seen: list = []
        new_header: list = []
        
        # Loop through each old column name
        for head in new_header_orig:
            
            # Check if the current column/head appears twice (or more) and whether it has already seen or not in that loop
            if head in doubles and head in seen:
                
                # If it is a double and it has been seen, that means the current header is the one belonging to the 'TO'
                new_header += [head + self.whitespace_replacer + TO_version_str]
            
            elif head in doubles:
                
                # If it has NOT been seen but it is a double, it is the one from 'FROM'
                new_header += [head + self.whitespace_replacer + FROM_version_str]
                
            else:
                # Otherwise, we leave the head as it is and append it to the list
                new_header += [head]
            
            # At the end of the loop, we update the variables
            seen += [head]
            # all_headers += [head]
        
        
        # We now remove the first rows which we don't need anymore
        df: pd.DataFrame = df_orig.copy().fillna("").iloc[new_header_idx+1:len(df_orig)]
        
        # Add new headers to the dataframe
        df.columns = new_header
        
        # Check if column names exist and extract the column names in the excel file
        FROM_colname_actID: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in actID_cols],
                                                                                                            in_list = new_header,
                                                                                                            raise_error_if_not_exist = True,
                                                                                                            return_element_if_not_exists = None)
        
        TO_colname_actID: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in actID_cols],
                                                                                                          in_list = new_header,
                                                                                                          raise_error_if_not_exist = True,
                                                                                                          return_element_if_not_exists = None)
        
        FROM_colname_prodID: (str | None) = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in prodID_cols],
                                                                                                                      in_list = new_header,
                                                                                                                      raise_error_if_not_exist = False,
                                                                                                                      return_element_if_not_exists = None)
        
        TO_colname_prodID: (str | None) = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in prodID_cols],
                                                                                                                    in_list = new_header,
                                                                                                                    raise_error_if_not_exist = False,
                                                                                                                    return_element_if_not_exists = None)
        
        FROM_colname_ref: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in ref_cols],
                                                                                                          in_list = new_header,
                                                                                                          raise_error_if_not_exist = True,
                                                                                                          return_element_if_not_exists = None)
        
        TO_colname_ref: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in ref_cols],
                                                                                                        in_list = new_header,
                                                                                                        raise_error_if_not_exist = True,
                                                                                                        return_element_if_not_exists = None)
        
        FROM_colname_act: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in act_cols],
                                                                                                          in_list = new_header,
                                                                                                          raise_error_if_not_exist = True,
                                                                                                          return_element_if_not_exists = None)
        
        TO_colname_act: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in act_cols],
                                                                                                        in_list = new_header,
                                                                                                        raise_error_if_not_exist = True,
                                                                                                        return_element_if_not_exists = None)
        
        FROM_colname_loc: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in loc_cols],
                                                                                                          in_list = new_header,
                                                                                                          raise_error_if_not_exist = True,
                                                                                                          return_element_if_not_exists = None)
        
        TO_colname_loc: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in loc_cols],
                                                                                                        in_list = new_header,
                                                                                                        raise_error_if_not_exist = True,
                                                                                                        return_element_if_not_exists = None)
        
        FROM_colname_unit: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, FROM_version_str)) for m in unit_cols],
                                                                                                           in_list = new_header,
                                                                                                           raise_error_if_not_exist = True,
                                                                                                           return_element_if_not_exists = None)
        
        TO_colname_unit: str = self.check_if_at_least_one_item_exists_in_list_and_return_first_occurence(items = [self.whitespace_replacer.join((m, TO_version_str)) for m in unit_cols],
                                                                                                         in_list = new_header,
                                                                                                         raise_error_if_not_exist = True,
                                                                                                         return_element_if_not_exists = None)
        
        # Extract column for the multiplier separately
        colname_mult_orig: list[str] = [m for m in mult_cols if m in new_header]
        
        # Raise error if the multiplier column was not found
        assert len(colname_mult_orig) > 0, "No multiplier column found. Used possible columns '{}'. Error occured in file '{}'".format(mult_cols, filepath_correspondence_excel)
        
        # Use the first element as column name for multiplier
        colname_mult: (int | float | str) = colname_mult_orig[0]
        
        if FROM_version not in self.raw_data:
            self.raw_data[FROM_version]: dict = {}
            
        if TO_version not in self.raw_data[FROM_version]:
            self.raw_data[FROM_version][TO_version]: dict = {}
        
        if FROM_version not in self.check_multipliers:
            self.check_multipliers[FROM_version]: dict = {}
            
        if TO_version not in self.check_multipliers[FROM_version]:
            self.check_multipliers[FROM_version][TO_version]: dict = {}
        
        # Loop through all entries in the dataframe
        for idx, row in df.iterrows():
            
            # Write column values to variables
            FROM_actID, TO_actID = row.get(FROM_colname_actID), row.get(TO_colname_actID)
            FROM_prodID, TO_prodID = row.get(FROM_colname_prodID), row.get(TO_colname_prodID)
            FROM_ref, TO_ref = row.get(FROM_colname_ref), row.get(TO_colname_ref)
            FROM_act, TO_act = row.get(FROM_colname_act), row.get(TO_colname_act)
            FROM_loc, TO_loc = row.get(FROM_colname_loc), row.get(TO_colname_loc)
            FROM_unit_orig, TO_unit_orig = row.get(FROM_colname_unit), row.get(TO_colname_unit)
            multiplier = row.get(colname_mult)
            
            # Use normalize unit function from Brightway
            FROM_unit, TO_unit = normalize_units_function(FROM_unit_orig), normalize_units_function(TO_unit_orig)
            
            # There might be cases where the multiplier is not a number
            # We need to handle such exceptions explicitely
            if not isinstance(multiplier, (int | float)):
                
                # Let's handle how to manage the multiplier if it is a text
                if isinstance(multiplier, str):
                
                    # If it is an empty text string, we can (safely?) assume that it is a 1
                    if multiplier.strip() == "":
                        multiplier: float = float(1)
                    
                    # Newly introduced datasets actually do not need a multiplier, but we use here a 1 as a placeholder
                    elif multiplier.strip().lower() == "new":
                        multiplier: float = float(1)
                      
                    # In the case where we find "no recommended share", we set the multiplier to 0. That means, those activities will not be mapped further (see code below).
                    elif re.search("no recommended share", multiplier.strip().lower()):
                        multiplier: float = float(0)
                    
                    else:
                        # For any other text that we do not yet capture, we raise an error to see how to deal with it
                        raise ValueError("Strange text multiplier specified in correspondence file '{}'. No rule has been defined on how to handle the mulitplier '{}' yet.".format(filename, multiplier))
                        
                else:
                    # If the multiplier is something else than a text, let's raise an error. We need to define new rules if that happens.
                    raise ValueError("Multiplier's type ('{}') is not a number and no rules have been set to handle it right now.".format(type(multiplier)))
            
            
            # Create FROM_ID
            FROM_ID: tuple = (FROM_actID,
                              FROM_prodID,
                              FROM_ref,
                              FROM_act,
                              FROM_loc,
                              FROM_unit
                              )
                               
            # Create TO_ID
            TO_ID: tuple = (TO_actID,
                            TO_prodID,
                            TO_ref,
                            TO_act,
                            TO_loc,
                            TO_unit
                            )
            
            # Initialize ID in dictionary if not yet existing
            if FROM_ID not in self.check_multipliers[FROM_version][TO_version]:
                self.check_multipliers[FROM_version][TO_version][FROM_ID]: float = float(multiplier)
                
            else:
                # Add to multipliers checking dictionary
                self.check_multipliers[FROM_version][TO_version][FROM_ID] += float(multiplier)
            
            
            # !!! We need to do the inverse for the multiplier. Do we???
            # According to the documentation from correspondence file v3.4/v3.5 (comment of cell N3)
            # If the multiplier is 1 it means the eiv3.4 activity is replaced by exactly one activity in eiv3.5.
            # If the multiplier is different (below one) it represents the share of the replacement activity.
            # E.g. if the value here is 0.25 then 25% of the eiv3.4 activity should be replaced by the specific activity in eiv3.5.
            # The share of the eiv3.4 matches of course sum up to 1.
            # inversed_multiplier: (int | float) = 1 / multiplier if multiplier != 0 else 0
            
            # Create ID
            ID: tuple = FROM_ID + TO_ID
            
            # Raise error if key is already available
            assert ID not in self.raw_data[FROM_version][TO_version], "Key is already present. Error occured for key '{}' when reading file '{}'".format(ID, filepath_correspondence_excel)
                
            # Append to data dictionary
            self.raw_data[FROM_version][TO_version][ID]: dict = {
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_version)): FROM_version,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_activity_uuid)): FROM_actID,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_reference_product_uuid)): FROM_prodID,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_activity_name)): FROM_act,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_reference_product_name)): FROM_ref,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_location_name)): FROM_loc,
                self.whitespace_replacer.join((self.FROM_definer, self.key_name_unit_name)): FROM_unit,
                self.key_name_multiplier: multiplier,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_version)): TO_version,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_activity_uuid)): TO_actID,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_reference_product_uuid)): TO_prodID,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_activity_name)): TO_act,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_reference_product_name)): TO_ref,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_location_name)): TO_loc,
                self.whitespace_replacer.join((self.TO_definer, self.key_name_unit_name)): TO_unit,
                }
    
    def check_if_multipliers_sum_to_1(self) -> list[dict]:
        
        problematic_data: dict = {(FROM_version, ID, TO_version): v for FROM_version, m in self.check_multipliers.items() for TO_version, n in m.items() for ID, v in n.items() if (v < 0.99 or v > 1.01) and (v != 0) and ("" not in ID) and (None not in ID)}
        multipliers_not_summing_to_1: list[dict] = []
        
        for (FROM_version, ID, TO_version), multiplier_summed in problematic_data.items():
            multipliers_not_summing_to_1 += [{**self.raw_data[FROM_version][TO_version][ID], **{"multiplier_summed": multiplier_summed}}]
        
        return multipliers_not_summing_to_1
        

    # Used here to identify if columns exist or not
    def check_if_at_least_one_item_exists_in_list_and_return_first_occurence(self,
                                                                             items: list,
                                                                             in_list: list,
                                                                             raise_error_if_not_exist: bool,
                                                                             return_element_if_not_exists: (str | float | None) = None) -> list:
        
        # Identify the items that can not be found in the list
        found: list = [m for m in items if m in in_list]
        
        # Check if error should be raised
        if raise_error_if_not_exist:
            
            # If at least one element has been found, raise error
            if len(found) == 0:
                raise ValueError("None of the item(s) '{}' can be found in list '{}'".format(items, in_list))
        
        # Return the elements and replace if they are not found
        return found[0] if len(found) > 0 else return_element_if_not_exists
    
    
    def _data_to_long_list(self) -> None:
        
        # Return if no raw data was found
        if self.raw_data == {}:
            self.all_data: list[dict] = []
            return
        
        # Write all data to a long list
        self.all_data: list[dict] = [{**{self.key_name_FROM_version: a},
                                      **e, **{self.key_name_TO_version: c}} for a, b in self.raw_data.items() for c, d in b.items() for _, e in d.items()]
    
    @property
    def standardized_df(self) -> pd.DataFrame:
        
        # Write the all data attribute
        self._data_to_long_list()
        
        # Return the dataframe
        return pd.DataFrame(self.all_data)
    
    
    def interlink_correspondence_files(self,
                                       FROM_version: tuple[int, int],
                                       TO_version: tuple[int, int]) -> None:
        
        # Go on if there is no 
        if FROM_version not in self.raw_data:
            return
        
        # Return if FROM_version is greater than the version we should map to
        if FROM_version >= TO_version:
            return
        
        # Initialize new attributes if not yet existing
        if not hasattr(self, "df_interlinked_data"):
            self.df_interlinked_data: dict = {}
            
        if not hasattr(self, "df_failed_interlinktion"):
            self.df_failed_interlinktion: dict = {}
        
        if not hasattr(self, "df_deleted"):
            self.df_deleted: dict = {}
            
        if not hasattr(self, "df_newly_introduced"):
            self.df_newly_introduced: dict = {}
        
        # If interlinktion already exists, simply return
        if FROM_version in self.df_interlinked_data:
            if TO_version in self.df_interlinked_data[FROM_version]:
                return
        
        # Write raw data to long list
        self._data_to_long_list()
        
        # Query the data we want to map, excluding the entries that have a multiplier of 0
        data: list[dict] = [m for m in self.all_data if m[self.key_name_FROM_version] == FROM_version and m[self.key_name_multiplier] != 0]    
        
        # Replace the NaN's with None
        df_all_data: pd.DataFrame = pd.DataFrame(self.all_data).replace({"": None})
        df_data: pd.DataFrame = pd.DataFrame(data).replace({"": None})
        
        # Initialize counter
        counter: int = 1
        counters: list[int] = []
        
        # !!! Add the first counter to the dataframe
        df_data.columns = [self.whitespace_replacer.join((m, str(counter))) for m in list(df_data.columns).copy()]
        
        # Print statement
        print("\nInterlinking versions:")
        
        # Print first version to console
        print(list(set(df_data[self.whitespace_replacer.join((self.key_name_FROM_version, str(counter)))].dropna()))[0], end = " ")
        
        # Go into a while loop
        while True:
            
            # Add current counter to list
            counters += [counter]
            
            # Print current version to console
            print("-->", list(set(df_data[self.whitespace_replacer.join((self.key_name_TO_version, str(counter)))].dropna()))[0], end = " ")
            
            # First set of columns to join the dataframes on
            left_on_1: list[str] = [self.whitespace_replacer.join((m, str(counter))) for m in (self.key_name_TO_version,) + self.TO_identifier_2]
            right_on_1: list[str] = [self.whitespace_replacer.join((m, str(counter + 1))) for m in (self.key_name_FROM_version,) + self.FROM_identifier_2]
            
            # Exclude rows that have incomplete identifier columns
            mask_1: pd.Series = df_data.copy()[left_on_1].isna().any(axis = 1) | (df_data.copy()[left_on_1] == "").any(axis = 1)
            excluded_1: pd.DataFrame = df_data.copy()[mask_1]
            df_data: pd.DataFrame = df_data.copy()[~mask_1]
            
            # Merge data on first identifier columns
            df_data: pd.DataFrame = df_data.copy().merge(
                df_all_data.copy().add_suffix(self.whitespace_replacer + str(counter + 1)),
                how = "left",
                left_on = left_on_1,
                right_on = right_on_1,
            )
            
            # Check which of the columns were not properly matched
            # We then continue with only the unmatched data and try to match it with the other identifier columns
            unmatched: pd.Series = df_data.copy()[right_on_1].isna().any(axis = 1)
            unmatched_df: pd.DataFrame = df_data.copy()[unmatched].drop(columns = df_data.copy().filter(regex = self.whitespace_replacer + str(counter + 1) + "$").columns)
            
            # Second set of columns to join the dataframes on
            left_on_2: list[str] = [self.whitespace_replacer.join((m, str(counter))) for m in (self.key_name_TO_version,) + self.TO_identifier_1]
            right_on_2: list[str] = [self.whitespace_replacer.join((m, str(counter + 1))) for m in (self.key_name_FROM_version,) + self.FROM_identifier_1]
            
            # Exclude rows that have incomplete identifier columns
            mask_2: pd.Series = unmatched_df.copy()[left_on_2].isna().any(axis = 1) | (unmatched_df.copy()[left_on_2] == "").any(axis = 1)
            excluded_2: pd.DataFrame = unmatched_df.copy()[mask_2]
            unmatched_df: pd.DataFrame = unmatched_df.copy()[~mask_2]
            
            # Merge on second set of identifier columns
            matched_df: pd.DataFrame = unmatched_df.copy().merge(
                df_all_data.copy().add_suffix(self.whitespace_replacer + str(counter + 1)),
                how = "left",
                left_on = left_on_2,
                right_on = right_on_2,
            )
            
            # Lets combine everything again
            # The unmatched, matched and excluded data
            df_data: pd.DataFrame = pd.concat([df_data.copy()[~unmatched],
                                               matched_df.copy(),
                                               excluded_1.copy(),
                                               excluded_2.copy()])
            
            # If we encounter only empty columns that have been newly attached to our df, that means we can end the while loop
            if df_data[right_on_1 + right_on_2].isna().all().all():
                
                # We drop the last columns that were added again and then break the while loop
                df_data: pd.DataFrame = df_data.copy().drop(columns = df_data.copy().filter(regex = self.whitespace_replacer + str(counter + 1) + "$").columns)
                break
            
            # The same happens if we have reached our final version we want to map to
            if TO_version in set(df_data.copy()[self.whitespace_replacer.join((self.TO_definer, self.key_name_version, str(counter)))]):
                
                # We drop the last columns that were added again and then break the while loop
                df_data: pd.DataFrame = df_data.copy().drop(columns = df_data.copy().filter(regex = self.whitespace_replacer + str(counter + 1) + "$").columns)
                break
            
            # !!! This is purely a saftey step! In case that we would not end the while loop, we break it manually after n steps and raise an error
            if counter == 50:
                raise ValueError("Aborted manually, was not breaking out of the while loop!")
            
            # Raise counter at the end
            counter += 1
        
        # Print empty line because end statement is ''
        print()
        
        # Let's replace the NaN's with None's to better be able to work with!
        df_data: pd.DataFrame = df_data.copy().replace({float("NaN"): None})
        
        # We construct the multiplier by multiplying all multipliers that were used ('prod')
        df_data[self.key_name_multiplier_uppered]: pd.Series = df_data.copy().filter(regex = self.key_name_multiplier).prod(axis = 1).astype(float)
        
        # We then add the current dataframe as raw results to the dictionary
        self.df_interlinked_data_raw[(FROM_version, TO_version)] = df_data.copy()
        
        # In order to understand what has happened during interlinking, we merge all the multiplier columns together using a '*'
        df_data.copy()[self.key_name_multiplier_uppered_plural]: pd.Series = df_data.copy().filter(regex = self.key_name_multiplier).astype(str).agg(" * ".join, axis = 1)
        
        # Similarly as for the multiplier, we'd like to understand what happened in between with all the other fields when interlinking
        # We loop through all the identifier columns and merge the together
        for i in (self.key_name_version,) + self.identifier_2 + self.identifier_1:
            df_data[i[0].upper() + i[1:].lower()]: pd.Series = df_data.copy().filter(regex = "{}{}{}{}{}$|{}{}{}".format(self.FROM_definer, self.whitespace_replacer, i, self.whitespace_replacer, min(counters), self.TO_definer, self.whitespace_replacer, i)).astype(str).agg(" -> ".join, axis = 1)
        
        # Now we only keep the columns with the minimum and maximum counter at the end of the column name,
        # ... plus the ones that we introduced beforehand
        # We use regex to do that...
        # !!! df_data: pd.DataFrame = df_data.copy().filter(regex = "(^FROM_(.*)_{}$)|(^TO_(.*)_{}$)|^Multiplier|{}".format(min(counters), max(counters), "|".join(["(^" + m[0].upper() + m[1:].lower() + "$)" for m in cols_1 + cols_2_without_version])))        
        df_data: pd.DataFrame = df_data.copy().filter(regex = "(^{}{}(.*){}{}$)|(^{}{}(.*){}{}$)|^{}|{}".format(self.FROM_definer, self.whitespace_replacer, self.whitespace_replacer, min(counters), self.TO_definer, self.whitespace_replacer, self.whitespace_replacer, max(counters), self.key_name_multiplier_uppered, "|".join(["(^" + m + "$)" for m in (self.key_name_version_uppered,) + self.identifier_2_uppered + self.identifier_1_uppered])))        
        
        # We remove the numbers at the end of the column names again, since we do not need them anymore
        df_data.columns = df_data.copy().columns.str.replace(self.whitespace_replacer + "[0-9]+$", "", regex = True)
        
        # Write the data where interlinktion failed to separate dataframe/dictionary
        # First we extract the data where interlinktion failed
        # This is by default the ones where either multiplier is 0, or the TO version is empty or not at the level where we want it to be
        interlinktion_failed: pd.Series = (df_data.copy()[self.key_name_TO_version].isna()) | (df_data.copy()[self.key_name_TO_version] != TO_version) | (df_data.copy()[self.key_name_multiplier_uppered] == 0)
        df_where_interlinktion_failed: pd.DataFrame = df_data.copy()[interlinktion_failed]
        df_data: pd.DataFrame = df_data.copy()[~interlinktion_failed]
        
        # Write the data which was deleted from one version to another to a separate dataframe
        # This is by default the ones where all TO columns are empty
        deleted: pd.Series = df_data.copy().filter(regex = "|".join(self.TO_identifier_2 + self.TO_identifier_1)).isna().all(axis = 1)
        df_deleted: pd.DataFrame = df_data.copy()[deleted]
        df_data: pd.DataFrame = df_data.copy()[~deleted]
        
        # Write the data which was newly introduced from one to another version to a separate dataframe
        # This is by default the ones where all FROM columns are empty
        newly_introduced: pd.Series = df_data.copy().filter(regex = "|".join(self.FROM_identifier_2 + self.FROM_identifier_1)).isna().all(axis = 1)
        df_newly_introduced: pd.DataFrame = df_data.copy()[newly_introduced]
        df_data: pd.DataFrame = df_data.copy()[~newly_introduced]
        
        # Add to self object
        self.df_interlinked_data[(FROM_version, TO_version)]: pd.DataFrame = df_data.copy()
        self.df_failed_interlinktion[(FROM_version, TO_version)]: pd.DataFrame = df_where_interlinktion_failed.copy()
        self.df_deleted[(FROM_version, TO_version)]: pd.DataFrame = df_deleted.copy()
        self.df_newly_introduced[(FROM_version, TO_version)]: pd.DataFrame = df_newly_introduced.copy()
    
                
        
#%%

if __name__ == "__main__":
    files: list[tuple] = [("Correspondence-File-v3.1-v3.2.xlsx", (3, 1), (3, 2)),
                          ("Correspondence-File-v3.2-v3.3.xlsx", (3, 2), (3, 3)),
                          ("Correspondence-File-v3.3-v3.4.xlsx", (3, 3), (3, 4)),
                          # ("Correspondence-File-v3.4-v3.5.xlsx", (3, 4), (3, 5)),
                          # ("Correspondence-File-v3.5-v3.6.xlsx", (3, 5), (3, 6)),
                          # ("Correspondence-File-v3.6-v3.7.1.xlsx", (3, 6), (3, 7, 1)),
                          # ("Correspondence-File-v3.7.1-v3.8.xlsx", (3, 7, 1), (3, 8)),
                          # ("Correspondence-File-v3.8-v3.9.1.xlsx", (3, 8), (3, 9, 1)),
                          # ("Correspondence-File-v3.8-v3.9.xlsx", (3, 8), (3, 9)),
                          # ("Correspondence-File-v3.9.1-v3.10.xlsx", (3, 9, 1), (3, 10)),
                          # ("Correspondence-File-v3.10.1-v3.11.xlsx", (3, 10, 1), (3, 11)),
                          # ("Correspondence-File-v3.10-v3.10.1.xlsx", (3, 10), (3, 10, 1)),
                          # ("Correspondence-File-v3.11-v3.12.xlsx", (3, 11), (3, 12)),
                          ]
    
    correspondence: Correspondence = Correspondence(ecoinvent_model_type = "cutoff")
    
    for filename, FROM_version, TO_version in files:       
        correspondence.read_correspondence_dataframe(filepath_correspondence_excel = here.parents[3] / "data" / "correspondence" / filename,
                                                     FROM_version = FROM_version,
                                                     TO_version = TO_version
                                                     )
    
    correspondence_raw_data: dict = correspondence.raw_data
    
    correspondence.interlink_correspondence_files((3, 1), (3, 4))
    # correspondence.interlink_correspondence_files((3, 5), (3, 12))
    # correspondence.interlink_correspondence_files((3, 8), (3, 12))
    # correspondence.interlink_correspondence_files((3, 8), (3, 10))
    
    df_multipliers_not_summing_to_1: pd.DataFrame = pd.DataFrame(correspondence.check_if_multipliers_sum_to_1())
    df_multipliers_not_summing_to_1.to_excel(here / "multipliers_not_summing_to_1_new.xlsx", index = False)
    
    df_interlinked_data: dict[tuple, pd.DataFrame] = correspondence.df_interlinked_data
    # df_interlinked_data[((3, 1), (3, 4))].to_excel(here / "correspondence_31_to_34.xlsx")
    # df_interlinked_data[((3, 8), (3, 12))].to_excel(here / "correspondence_38_to_312.xlsx")
    # df_interlinked_data[((3, 8), (3, 10))].to_excel(here / "correspondence_38_to_310.xlsx")


    
