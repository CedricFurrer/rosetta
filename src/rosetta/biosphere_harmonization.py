import torch
import pathlib
from . import helper as hp
from dataclasses import asdict
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from typing import Optional, Callable
from sentence_transformers import SentenceTransformer, util

@dataclass(frozen = True)
class BiosphereDefinition:
    biosphere_code: Optional[str] = None
    name: Optional[str] = None
    simapro_name: Optional[str] = None
    cas_number: Optional[str] = None
    top_category: Optional[str] = None
    sub_category: Optional[str] = None
    location: Optional[str] = None
    unit: Optional[str] = None
    
    @field_validator("biosphere_code",
                     "name",
                     "simapro_name",
                     "top_category",
                     "sub_category"
                     "unit",
                     mode = "before")
    def ensure_string(cls, value) -> (str | None):
        if not isinstance(value, str) or value.strip() == "":
            return None
        return value
    
    @field_validator("location",
                     mode = "before")
    def ensure_GLO(cls, value) -> str:
        if not isinstance(value, str) or value.strip() == "":
            return "GLO"
        return value
    
    @field_validator("location",
                     mode = "before")
    def ensure_correct_CAS(cls, value) -> (str | None):
        if not isinstance(value, str) or value.strip() == "":
            return None
        return hp.give_back_correct_cas(cas_value = value, return_None = True)
    
    @property
    def ID(cls):
        return tuple(cls.__dict__.values())
    
    @property
    def data(cls) -> dict:
        return asdict(cls)

@dataclass(frozen = True)
class Multiplier:
    multiplier: (float | None) = float(1)
    
    @field_validator("multiplier", mode = "before")
    def is_1_if_None(cls, value: (float | None)) -> float:
        return float(1) if value is None else value


def direct_on_biocode(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.biosphere_code,)]

def direct_on_name_topcat_subcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.name, bio.topcat, bio.subcat, bio.location, bio.unit)]

def direct_on_SimaPro_name_topcat_subcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.simapro_name, bio.topcat, bio.subcat, bio.location, bio.unit)]

def direct_on_created_SimaPro_name_topcat_subcat_unit(bio: BiosphereDefinition) -> list[tuple]:
    if isinstance(bio.name, str) and isinstance(bio.location, str):
        return ("{}, {}".format(bio.name, bio.location), bio.topcat, bio.subcat, bio.unit)
    else:
        (None, bio.topcat, bio.subcat, bio.location, bio.unit)

def direct_on_CAS_topcat_subcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.cas_number, bio.topcat, bio.subcat, bio.location, bio.unit)]

def direct_on_name_topcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.name, bio.topcat, "unspecified", bio.location, bio.unit)]

def direct_on_SimaPro_name_topcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.simapro_name, bio.topcat, "unspecified", bio.location, bio.unit)]

def direct_on_created_SimaPro_name_topcat_unit(bio: BiosphereDefinition) -> list[tuple]:
    if isinstance(bio.name, str) and isinstance(bio.location, str):
        return ("{}, {}".format(bio.name, bio.location), bio.topcat, "unspecified", bio.unit)
    else:
        return (None, bio.topcat, "unspecified", bio.location, bio.unit)

def direct_on_CAS_topcat_location_unit(bio: BiosphereDefinition) -> list[tuple]:
    return [(bio.cas_number, bio.topcat, "unspecified", bio.location, bio.unit)]


def get_SBERT_options(bio: BiosphereDefinition) -> tuple[str]:
    
    options: list = []
    
    if isinstance(bio.name, str) and isinstance(bio.topcat, str) and isinstance(bio.subcat, str) and isinstance(bio.location, str) and isinstance(bio.unit, str):
        options += [(bio.name, bio.topcat, bio.subcat, bio.location, bio.unit)]
    
    if isinstance(bio.simapro_name, str) and isinstance(bio.topcat, str) and isinstance(bio.subcat, str) and isinstance(bio.location, str) and isinstance(bio.unit, str):
        options += [(bio.simapro_name, bio.topcat, bio.subcat, bio.location, bio.unit)]
        
    if isinstance(bio.name, str) and isinstance(bio.topcat, str) and isinstance(bio.location, str) and isinstance(bio.unit, str):
        options += [(bio.name, bio.topcat, bio.location, bio.unit)]
        
    if isinstance(bio.simapro_name, str) and isinstance(bio.topcat, str) and isinstance(bio.location, str) and isinstance(bio.unit, str):
        options += [(bio.simapro_name, bio.topcat, bio.location, bio.unit)]
    
    return tuple([", ".join(m) for m in options])
        

        
DEFAULT_PATH_TO_SBERT_MODEL: pathlib.Path = pathlib.Path(__file__).parent / "defaults" / "all-MiniLM-L6-v2"

class BiosphereHarmonization:
    
    def __init__(self):

        self._source_definitions: dict = {}
        self._target_definitions: dict = {}
        self._mappings_dict: dict = {}
        
        self._mapping_type_direct: str = "direct"
        self._mapping_type_cas: str = "cas"
        self._mapping_type_custom: str = "custom"
        self._mapping_type_sbert: str = "SBERT"
        self._encoded_TOs = None
        
        # “rules” are key functions
        self._rule_fns: dict[str, Callable[BiosphereDefinition, tuple]] = {
            "direct_on_biocode": direct_on_biocode,
            "direct_on_name_topcat_subcat_location_unit": direct_on_name_topcat_subcat_location_unit,
            "direct_on_SimaPro_name_topcat_subcat_location_unit": direct_on_SimaPro_name_topcat_subcat_location_unit,
            "direct_on_created_SimaPro_name_topcat_subcat_unit": direct_on_created_SimaPro_name_topcat_subcat_unit,
            "direct_on_CAS_topcat_subcat_location_unit": direct_on_CAS_topcat_subcat_location_unit,
            "direct_on_name_topcat_location_unit": direct_on_name_topcat_location_unit,
            "direct_on_SimaPro_name_topcat_location_unit": direct_on_SimaPro_name_topcat_location_unit,
            "direct_on_created_SimaPro_name_topcat_unit": direct_on_created_SimaPro_name_topcat_unit,
            "direct_on_CAS_topcat_location_unit": direct_on_CAS_topcat_location_unit
         }
    
    @property
    def direct_mapping(self) -> dict:
        none_query: BiosphereDefinition = BiosphereDefinition()
        self.map_directly(query = none_query)
        return self._mappings_dict[self._mapping_type_direct]
    
    @property
    def custom_mapping(self) -> dict:
        none_query: BiosphereDefinition = BiosphereDefinition()
        self.map_using_custom_mapping(query = none_query)
        return self._mappings_dict[self._mapping_type_custom]
    
    @property
    def cas_mapping(self) -> dict:
        none_query: BiosphereDefinition = BiosphereDefinition()
        self.map_using_correspondence_mapping(query = none_query)
        return self._mappings_dict[self._mapping_type_correspondence]
    
    @property
    def SBERT_mapping(self) -> dict:
        none_query: BiosphereDefinition = BiosphereDefinition()
        self.map_using_SBERT_mapping(queries = [none_query])
        return self._mappings_dict[self._mapping_type_sbert]
    
    def add_TO(self,
               source: BiosphereDefinition,
               target: dict,
               multiplier: (float | None)
               ) -> None:
        
        self._add_to_mapping(mapping_type = self._mapping_type_direct,
                             source = source,
                             target = target,
                             multiplier = multiplier)
        
        self._encoded_TOs = None
    
    
    def add_to_custom_mapping(self,
                              source: BiosphereDefinition,
                              target: BiosphereDefinition,
                              multiplier: (float | None)
                              ) -> None:
        
        updated_target_dict: dict = {}
        for attr, value in vars(target).items():
            if value is None:
                updated_target_dict[attr]: (str | None) = getattr(source, attr)
            else:
                updated_target_dict[attr]: (str | None) = value
        
        updated_target: BiosphereDefinition = BiosphereDefinition(**updated_target_dict)
        
        self._add_to_mapping(mapping_type = self._mapping_type_custom,
                             source = source,
                             target = updated_target,
                             multiplier = multiplier
                             )
        
    
    def add_to_cas_mapping(self,
                           source: BiosphereDefinition,
                           target: BiosphereDefinition,
                           multiplier: (float | None)
                           ) -> None:
        
        self._add_to_mapping(mapping_type = self._mapping_type_cas,
                             source = source,
                             target = target,
                             multiplier = multiplier
                             )
    
    def map_directly(self,
                     query: BiosphereDefinition
                     ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        # Currently, we use all rules as a default. Can be changed however.
        direct_rules: tuple[str] = tuple(list(self._rule_fns.keys()))
        
        final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query,
                                                                mapping_type = self._mapping_type_direct,
                                                                rules = direct_rules,
                                                                multipliers_need_to_sum_to_1 = False)
        if final_found == ():
            return ()
        
        else:
            return ((query.data, tuple([(dct, mult.multiplier) for dct, mult in final_found])),)
        
    
    def map_using_custom_mapping(self,
                                 query: BiosphereDefinition
                                 ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        # Currently, we use all rules as a default. Can be changed however.
        custom_rules: tuple[str] = tuple(list(self._rule_fns.keys()))
        
        founds: tuple[tuple[BiosphereDefinition, Multiplier]] = self._map(query = query,
                                                                          mapping_type = self._mapping_type_custom,
                                                                          rules = custom_rules,
                                                                          multipliers_need_to_sum_to_1 = False
                                                                          )
        final: tuple = ()
        for query_final, multiplier_final in founds:
            
            final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                    mapping_type = self._mapping_type_direct,
                                                                    rules = custom_rules,
                                                                    multipliers_need_to_sum_to_1 = False,
                                                                    )
            if final_found == ():
                return ()
            
            final += tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])
            
        return ((query.data, final),) if len(final) > 0 else ()
        
    
    def map_using_cas_mapping(self,
                              query: BiosphereDefinition,
                              ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        # Currently, we use all rules as a default. Can be changed however.
        cas_rules: tuple[str] = tuple(list(self._rule_fns.keys()))
        
        founds: tuple[tuple[BiosphereDefinition, Multiplier]] = self._map(query = query,
                                                                          mapping_type = self._mapping_type_cas,
                                                                          rules = cas_rules,
                                                                          multipliers_need_to_sum_to_1 = False
                                                                          )
        final: tuple = ()
        for query_final, multiplier_final in founds:
            
            final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                    mapping_type = self._mapping_type_direct,
                                                                    rules = cas_rules,
                                                                    multipliers_need_to_sum_to_1 = False,
                                                                    )
            if final_found == ():
                return ()
            
            final += tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])
            
        return ((query.data, final),) if len(final) > 0 else ()
            
    
    def map_using_SBERT_mapping(self,
                                queries: tuple[BiosphereDefinition],
                                path_to_model: (pathlib.Path | None) = DEFAULT_PATH_TO_SBERT_MODEL,
                                n: int = 3,
                                cutoff: float = 0.92
                                ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        if self._mapping_type_direct not in self._source_definitions:
            return ()
        
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load SBERT model
        if path_to_model is not None and path_to_model.exists():
            model = SentenceTransformer(str(path_to_model), device = device)
        else:
            model = SentenceTransformer("all-MiniLM-L6-v2", device = device)
                
        if self._encoded_TOs is None:
            self._TOs_prepared: tuple = ()
            self._backward_SBERT: dict = {}
            
            for target in list(self._source_definitions[self._mapping_type_direct].values()):
                SBERT_options: tuple[str] = get_SBERT_options(target)
                
                self._TOs_prepared += SBERT_options
                self._backward_SBERT |= {o: target.ID for o in SBERT_options}
                
                self._encoded_TOs = model.encode(self._TOs_prepared, convert_to_tensor = True)
        
        queries_prepared: tuple[tuple] = tuple([mm for m in queries for mm in get_SBERT_options(m)])
        
        if self._TOs_prepared == ():
            return ()

        embeddings1 = model.encode(queries_prepared, convert_to_tensor = True)
        
        # Compute cosine-similarities
        cosine_scores = util.cos_sim(embeddings1, self._encoded_TOs)
    
        # Loop through each item from 'items_to_map' and extract the elements that were mapped to it with its respective cosine score
        for idx, scores_tensor in enumerate(cosine_scores):
            
            # Extract the scores (values) and its respective location (indice)
            values, indices = torch.sort(scores_tensor, descending = True)
            
            # Add the n (max_number) mapped items with the highest cosine score to the list
            for ranking, value, indice in zip(reversed(range(1, n + 1)), values[0:n], indices[0:n]):
                
                if value < cutoff:
                    continue
                
                source: BiosphereDefinition = queries[idx]
                target: BiosphereDefinition = self._source_definitions[self._mapping_type_direct][self._backward_SBERT[self._TOs_prepared[indice]]]
                
                self._add_to_mapping(mapping_type = self._mapping_type_sbert,
                                     source = source,
                                     target = target,
                                     multiplier = float(1)
                                     )
        
        final: tuple = ()
        for query in queries:
            
            # Currently, we use all rules as a default. Can be changed however.
            sbert_rules: tuple[str] = tuple(list(self._rule_fns.keys()))
            
            founds: tuple[tuple[BiosphereDefinition, Multiplier]] = self._map(query = query,
                                                                              mapping_type = self._mapping_type_sbert,
                                                                              rules = sbert_rules,
                                                                              multipliers_need_to_sum_to_1 = True
                                                                             )
            for query_final, multiplier_final in founds:
                
                final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                        mapping_type = self._mapping_type_direct,
                                                                        rules = sbert_rules,
                                                                        multipliers_need_to_sum_to_1 = False,
                                                                        )
                if final_found == ():
                    return ()
                
                final += ((query.data, tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])),)
        
            
        return final


    def _add_to_mapping(self,
                        mapping_type: str,
                        source: BiosphereDefinition,
                        target: (BiosphereDefinition | dict),
                        multiplier: (float | None)) -> None:
        
        if mapping_type not in self._source_definitions:
            self._source_definitions[mapping_type]: dict = {}
            
        if mapping_type not in self._target_definitions:
            self._target_definitions[mapping_type]: dict = {}
        
        if source.ID not in self._source_definitions[mapping_type]:
            self._source_definitions[mapping_type][source.ID]: BiosphereDefinition = source
            self._target_definitions[mapping_type][source.ID]: tuple[tuple[(BiosphereDefinition | dict), Multiplier]] = ((target, Multiplier(multiplier = multiplier)),)
            
        else:
            self._target_definitions[mapping_type][source.ID] += ((target, Multiplier(multiplier = multiplier)),)
        
        # Since we add a new item, we need to reset the mapping dictionary
        self._mappings_dict[mapping_type]: dict = {}
        


    def _get_mapping_dict(self, mapping_type: str, rule: str) -> dict:
        
        if mapping_type not in self._target_definitions:
            return {}
        
        if mapping_type not in self._mappings_dict:
            self._mappings_dict[mapping_type]: dict = {}
        
        if rule in self._mappings_dict[mapping_type]:
            return self._mappings_dict[mapping_type][rule]
        
        else:
            self._mappings_dict[mapping_type][rule]: dict = {}
        
        if rule not in self._rule_fns:
            raise ValueError("Rule '{}' is not implemented".format(rule))
        
        rule_fn = self._rule_fns[rule]
        
        for source_ID, targets in self._target_definitions[mapping_type].items():
            
            source: BiosphereDefinition = self._source_definitions[mapping_type][source_ID]
            targets: tuple[tuple[BiosphereDefinition, Multiplier]] = self._target_definitions[mapping_type][source_ID]
            rule_tuples: tuple = rule_fn(source)
            
            for rule_tuple in rule_tuples:
                if not any([n is None for n in rule_tuple]):
                    self._mappings_dict[mapping_type][rule][rule_tuple] = targets
        
        return self._mappings_dict[mapping_type][rule]
    

    def _map(self,
             query: BiosphereDefinition,
             mapping_type: str,
             rules: tuple[str],
             multipliers_need_to_sum_to_1: bool,
             ) -> tuple[tuple[BiosphereDefinition | dict, Multiplier]]:
                
        for rule in rules:
            mapping: dict = self._get_mapping_dict(mapping_type = mapping_type, rule = rule)
            found: tuple[tuple[BiosphereDefinition, Multiplier]] = self._get_targets(query = query, rule = rule, mapping = mapping)
            
            if len(found) > 0:
                
                if multipliers_need_to_sum_to_1:
                    multipliers: list[float] = [m[1].multiplier for m in found]
                    
                    if multipliers == [] or sum(multipliers) != 1:
                        continue

                return found
            
        return ()
        

    def _get_targets(self, query: BiosphereDefinition, rule: str, mapping: dict) -> tuple[tuple[BiosphereDefinition | dict, Multiplier]]:
        rule_fn = self._rule_fns[rule]
        retrieved: list = [mapping[m] for m in rule_fn(query) if m in mapping]
        return retrieved[0] if len(retrieved) > 0 else ()
 

if __name__ == "__main__":
    
    ah: BiosphereHarmonization = BiosphereHarmonization()
    
    # custom_FROM_1 = BiosphereDefinition(name = "Product A",
    #                                     simapro_name = "Product A, RER",
    #                                     topcat = "air",
    #                                     subcat = "low pop.",
    #                                     unit = "kilogram",
    #                                     location = "CH"
    #                                     )
    
    # custom_TO_1 = BiosphereDefinition(activity_code = "actcodexxx",
    #                                  reference_product_code = "refcode0.25",
    #                                  activity_name = None,
    #                                  name = "Product B",
    #                                  unit = "ton",
    #                                  location = None
    #                                  )
    
    # custom_multiplier_1 = 0.001
    
    # corr_FROM_1 = ActivityDefinition(activity_code = "actcode1",
    #                                  reference_product_code = "refcode1",
    #                                  activity_name = "actname1",
    #                                  reference_product_name = "refname1",
    #                                  unit = "kilogram",
    #                                  location = "CH"
    #                                  )
    
    # # print(FROM_1.data)
    
    # corr_TO_11 = ActivityDefinition(activity_code = "actcodexxx",
    #                                 reference_product_code = "refcode0.25",
    #                                 unit = "meter"
    #                                 )
        
    # corr_multiplier_11 = 0.25
    
    # corr_TO_12 = ActivityDefinition(activity_code = "actcode0.75",
    #                                 reference_product_code = "refcode0.75",
    #                                 activity_name = "new_name",
    #                                 unit = "ton"
    #                                 )
    # corr_multiplier_12 = 0.75
    
    
    # to_map_FROM_11 = ActivityDefinition(activity_code = "actcodexxx",
    #                                     reference_product_code = "refcode0.25",
    #                                     name = "Product A",
    #                                     unit = "kilogram",
    #                                     location = "CH")
    
    # to_map_FROM_12 = ActivityDefinition(activity_code = "actcode0.75",
    #                                     reference_product_code = "refcode0.75",
    #                                     unit = "kilogram")
    
    # to_map_TO_1 = {"worked": "right"}
    # to_map_TO_2 = {"also": "here"}
    
    
    # query_1 = ActivityDefinition(activity_code = "actcode0.75",
    #                              reference_product_code = "refcode0.75",
    #                              activity_name = "actname11",
    #                              reference_product_name = "refname1",
    #                              unit = "kilogram",
    #                              location = "CH")
    
    # query_2 = ActivityDefinition(activity_code = "actcode1",
    #                              reference_product_code = "refcode1",
    #                              activity_name = "actname11",
    #                              reference_product_name = "refname1",
    #                              unit = "kilogram",
    #                              location = "CH")
    
    # query_3 = ActivityDefinition(activity_code = "actcode1",
    #                              reference_product_code = "refcode1",
    #                              activity_name = "actname11",
    #                              name = "Product A",
    #                              unit = "kilogram",
    #                              location = "CH")
    
    # query_4 = ActivityDefinition(activity_code = "actcode1",
    #                              reference_product_code = "refcode1",
    #                              activity_name = "actname11",
    #                              name = "Product AA",
    #                              unit = "kilogram",
    #                              location = "CH")
    
    # query_not_working = ActivityDefinition(activity_code = "xxxxx",
    #                                  reference_product_code = "xxxxxx",
    #                                  activity_name = "xxxx1",
    #                                  name = "Pxxxxx",
    #                                  unit = "xxxxxm",
    #                                  location = "xxxxxx")
    
    # ah.add_to_custom_mapping(source = custom_FROM_1, target = custom_TO_1, multiplier = custom_multiplier_1)
    # ah.add_to_correspondence_mapping(source = corr_FROM_1, target = corr_TO_11, multiplier = corr_multiplier_11)
    # ah.add_to_correspondence_mapping(source = corr_FROM_1, target = corr_TO_12, multiplier = corr_multiplier_12)
    # ah.add_TO(source = to_map_FROM_11, target = to_map_TO_11_1, multiplier = 0.48)
    # ah.add_TO(source = to_map_FROM_11, target = to_map_TO_11_2, multiplier = 0.52)
    # ah.add_TO(source = to_map_FROM_12, target = to_map_TO_12_1, multiplier = 1)

    
    # result_1: tuple[tuple[dict, float]] = ah.map_directly(query = query_1)
    # result_2: tuple[tuple[dict, float]] = ah.map_using_correspondence(query = query_2)
    # result_3: tuple[tuple[dict, float]] = ah.map_using_custom(query = query_3)
    # result_4: tuple[tuple[dict, float]] = ah.map_using_SBERT(queries = [query_4])
    
    # result_11: tuple[tuple[dict, float]] = ah.map_directly(query = query_not_working)
    # result_22: tuple[tuple[dict, float]] = ah.map_using_correspondence(query = query_not_working)
    # result_33: tuple[tuple[dict, float]] = ah.map_using_custom(query = query_not_working)
    # result_44: tuple[tuple[dict, float]] = ah.map_using_SBERT(queries = [query_not_working])
    
    
    
