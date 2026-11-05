import copy
import torch
import pathlib
from dataclasses import asdict
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from typing import Optional, Callable
from functools import partial
from sentence_transformers import SentenceTransformer, util

def prep(string: (str | None), lower: bool = True, strip: bool = True) -> (str | None):
    if isinstance(string, str):
        if lower and strip:
            return string.strip().lower()
        elif lower:
            return string.lower()
        elif strip:
            return string.strip()
        else:
            return string
    
    else:
        return string



@dataclass(frozen = True)
class ActivityDefinition:
    activity_code: Optional[str] = None
    reference_product_code: Optional[str] = None
    activity_name: Optional[str] = None
    reference_product_name: Optional[str] = None
    name: Optional[str] = None
    simapro_name: Optional[str] = None
    location: Optional[str] = None
    unit: Optional[str] = None
    
    @field_validator("activity_code",
                     "reference_product_code",
                     "activity_name",
                     "reference_product_name",
                     "name",
                     "simapro_name",
                     "location",
                     "unit",
                     mode = "before")
    def ensure_string(cls, value) -> (str | None):
        if not isinstance(value, str) or value.strip() == "":
            return None
        return value
    
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


def direct_on_actcode_refcode_unit(act: ActivityDefinition) -> list[tuple]:
    return [(act.activity_code, act.reference_product_code, act.unit)]

def direct_on_actcode_unit(act: ActivityDefinition) -> list[tuple]:
    if isinstance(act.activity_code, str) and act.reference_product_code is None:
        return [(act.activity_code, act.unit)]
    else:
        return []

def direct_on_actname_refname_location_unit(act: ActivityDefinition) -> list[tuple]:
    return [(prep(act.activity_name), prep(act.reference_product_name), act.location, prep(act.unit))]

def direct_on_refname_actname_location_unit(act: ActivityDefinition) -> list[tuple]:
    return [(prep(act.reference_product_name), prep(act.activity_name), act.location, prep(act.unit))]

def direct_on_name_location_unit(act: ActivityDefinition) -> list[tuple]:
    return [(prep(act.name), act.location, prep(act.unit))]

def direct_on_SimaPro_name_unit(act: ActivityDefinition) -> list[tuple]:
    return [(prep(act.simapro_name), prep(act.unit))]

def direct_on_combined_refname_actname_location_unit(act: ActivityDefinition) -> list[tuple]:
    if isinstance(act.reference_product_name, str) and isinstance(act.activity_name, str):
        return [(prep(act.reference_product_name), prep(act.reference_product_name) + ", " + prep(act.activity_name), act.location, prep(act.unit))]
    else:
        # return [(prep(act.reference_product_name), None, act.location, prep(act.unit))]
        return []
        
def direct_on_combined_actname_refname_location_unit(act: ActivityDefinition) -> list[tuple]:
    if isinstance(act.reference_product_name, str) and isinstance(act.activity_name, str):
        return [(prep(act.activity_name) + " " + prep(act.reference_product_name), prep(act.reference_product_name), act.location, prep(act.unit))]
    else:
        # return [(None, prep(act.reference_product_name), act.location, prep(act.unit))]
        return []
        
def direct_on_created_SimaPro_name_unit(act: ActivityDefinition, models: list[str], systems: list[str]) -> list[tuple]:
    
    lst: list[tuple] = []
    
    for model in models:
        
        if not isinstance(model, str):
            continue
        
        for system in systems:
            
            if not isinstance(system, str):
                continue
            
            fields: tuple = (act.reference_product_name, act.location, act.activity_name, model, system)
            
            if all([isinstance(m, str) for m in fields]):
                created_SimaPro_name: (str | None) = "{} {{{}}}| {} | {}, {}".format(fields[0], fields[1], fields[2], fields[3], fields[4])
                lst += [(prep(created_SimaPro_name), prep(act.unit))]
    
    return lst

def get_SBERT_options(act: ActivityDefinition) -> tuple[str]:
    
    options: list = []
    
    if isinstance(act.simapro_name, str) and isinstance(act.unit, str):
        options += [(prep(act.simapro_name), prep(act.unit))]
        
    if isinstance(act.reference_product_name, str) and isinstance(act.activity_name, str) and isinstance(act.unit, str) and isinstance(act.location, str):
        options += [(prep(act.activity_name), prep(act.reference_product_name), act.location, prep(act.unit))]
        
    if isinstance(act.name, str) and isinstance(act.unit, str) and isinstance(act.location, str):
        options += [(prep(act.name), act.location, prep(act.unit))]
        
    return tuple([", ".join(m) for m in options])
        
        
        
DEFAULT_PATH_TO_SBERT_MODEL: pathlib.Path = pathlib.Path(__file__).parent / "defaults" / "all-MiniLM-L6-v2"

class ActivityHarmonization:
    
    def __init__(self,
                 # model: str,
                 # system: str
                 ):
        
        # models: dict[str, list[str]] = {"Cut-off": ["Cut-off", "Cut-Off", "cutoff"],
        #                                 }
        
        # systems: dict[str, list[str]] = {"Unit": ["Unit", "U"],
        #                                  "System": ["System", "S"],
        #                                  }
        
        # if model not in models:
        #     raise ValueError("Specified model {} is not valid. Choose one of the following:\n - {}".format(model, "\n - ".join(list(models.keys()))))
        
        # if system not in systems:
        #     raise ValueError("Specified system {} is not valid. Choose one of the following:\n - {}".format(system, "\n - ".join(list(systems.keys()))))
        
        # self.models: list[str] = models[model]
        # self.systems: list[str] = systems[system]
        
        self.models: list[str] = ["Cut-off", "Cut-Off", "cutoff"]
        self.systems: list[str] = ["Unit", "unit", "U", "System", "system", "S"]
        
        self._source_definitions: dict = {}
        self._target_definitions: dict = {}
        self._mappings_dict: dict = {}
        self._mappings_dict_all: dict = {}
        
        self._mapping_type_direct: str = "direct"
        self._mapping_type_correspondence: str = "correspondence"
        self._mapping_type_custom: str = "custom"
        self._mapping_type_sbert: str = "SBERT"
        self._encoded_TOs = None
        
        # “rules” are key functions
        self._rule_fns: dict[str, Callable[ActivityDefinition, tuple]] = {
            "direct_on_actname_refname_location_unit": direct_on_actname_refname_location_unit,
            "direct_on_refname_actname_location_unit": direct_on_refname_actname_location_unit,
            "direct_on_actcode_refcode_unit": direct_on_actcode_refcode_unit,
            "direct_on_actcode_unit": direct_on_actcode_unit,
            "direct_on_name_location_unit": direct_on_name_location_unit,
            "direct_on_SimaPro_name_unit": direct_on_SimaPro_name_unit,
            "direct_on_created_SimaPro_name_unit": partial(direct_on_created_SimaPro_name_unit, models = self.models, systems = self.systems)   ,
            "direct_on_combined_refname_actname_location_unit": direct_on_combined_refname_actname_location_unit,
            "direct_on_combined_actname_refname_location_unit": direct_on_combined_actname_refname_location_unit
        }
        
        # Currently, we use all rules as a default. Can be changed however.
        self._rule_fns_direct: dict[str, Callable[ActivityDefinition, tuple]] = self._rule_fns.copy()
        self._rule_fns_custom: dict[str, Callable[ActivityDefinition, tuple]] = self._rule_fns.copy()
        self._rule_fns_correspondence: dict[str, Callable[ActivityDefinition, tuple]] = self._rule_fns.copy()
        self._rule_fns_sbert: dict[str, Callable[ActivityDefinition, tuple]] = self._rule_fns.copy()

    
    @property
    def direct_mapping(self) -> dict:
        none_query: ActivityDefinition = ActivityDefinition()
        self.map_directly(query = none_query)
        return self._mappings_dict.get(self._mapping_type_direct, {})
    
    @property
    def custom_mapping(self) -> dict:
        none_query: ActivityDefinition = ActivityDefinition()
        self.map_using_custom_mapping(query = none_query)
        return self._mappings_dict.get(self._mapping_type_custom, {})
    
    @property
    def correspondence_mapping(self) -> dict:
        none_query: ActivityDefinition = ActivityDefinition()
        self.map_using_correspondence_mapping(query = none_query)
        return self._mappings_dict.get(self._mapping_type_correspondence, {})
    
    @property
    def SBERT_mapping(self) -> dict:
        none_query: ActivityDefinition = ActivityDefinition()
        self.map_using_SBERT_mapping(queries = [none_query])
        return self._mappings_dict.get(self._mapping_type_sbert, {})
    
    @property
    def mapping_all(self) -> dict:
        dcts: list[dict]  = [self.direct_mapping, self.custom_mapping, self.correspondence_mapping, self.SBERT_mapping]
        mapping_all: dict = {}
        for dct in dcts:
            for k, v in dct.items():
                if k not in mapping_all:
                    mapping_all[k] = v
        return mapping_all
    
    def add_TO(self,
               source: ActivityDefinition,
               target: dict,
               multiplier: (float | None)
               ) -> None:
        
        self._add_to_mapping(mapping_type = self._mapping_type_direct,
                             source = source,
                             target = target,
                             multiplier = multiplier)
        
        self._encoded_TOs = None
    
    
    def add_to_custom_mapping(self,
                              source: ActivityDefinition,
                              target: ActivityDefinition,
                              multiplier: (float | None)
                              ) -> None:
        
        updated_target_dict: dict = {}
        for attr, value in vars(target).items():
            if value is None:
                updated_target_dict[attr]: (str | None) = getattr(source, attr)
            else:
                updated_target_dict[attr]: (str | None) = value
        
        updated_target: ActivityDefinition = ActivityDefinition(**updated_target_dict)
        
        self._add_to_mapping(mapping_type = self._mapping_type_custom,
                             source = source,
                             target = updated_target,
                             multiplier = multiplier
                             )
        
    
    def add_to_correspondence_mapping(self,
                                      source: ActivityDefinition,
                                      target: ActivityDefinition,
                                      multiplier: (float | None)
                                      ) -> None:
        
        self._add_to_mapping(mapping_type = self._mapping_type_correspondence,
                             source = source,
                             target = target,
                             multiplier = multiplier
                             )
    
    def map_directly(self,
                     query: ActivityDefinition
                     ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query,
                                                                mapping_type = self._mapping_type_direct,
                                                                rules = self._rule_fns_direct,
                                                                multipliers_need_to_sum_to_1 = False)
        if final_found == ():
            return ()
        
        else:
            return ((query.data, tuple([(dct, mult.multiplier) for dct, mult in final_found])),)
        
    
    def map_using_custom_mapping(self,
                                 query: ActivityDefinition
                                 ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        founds: tuple[tuple[ActivityDefinition, Multiplier]] = self._map(query = query,
                                                                         mapping_type = self._mapping_type_custom,
                                                                         rules = self._rule_fns_custom,
                                                                         multipliers_need_to_sum_to_1 = False
                                                                         )
        final: tuple = ()
        for query_final, multiplier_final in founds:
            
            final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                    mapping_type = self._mapping_type_direct,
                                                                    rules = self._rule_fns_direct,
                                                                    multipliers_need_to_sum_to_1 = False,
                                                                    )
            if final_found == ():
                return ()
            
            final += tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])
            
        return ((query.data, final),) if len(final) > 0 else ()
        
    
    def map_using_correspondence_mapping(self,
                                         query: ActivityDefinition,
                                         ) -> tuple[tuple[dict, tuple[dict, float]]]:
        
        founds: tuple[tuple[ActivityDefinition, Multiplier]] = self._map(query = query,
                                                                         mapping_type = self._mapping_type_correspondence,
                                                                         rules = self._rule_fns_correspondence,
                                                                         multipliers_need_to_sum_to_1 = True
                                                                         )
        final: tuple = ()
        for query_final, multiplier_final in founds:
            
            final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                    mapping_type = self._mapping_type_direct,
                                                                    rules = self._rule_fns_direct,
                                                                    multipliers_need_to_sum_to_1 = False,
                                                                    )
            if final_found == ():
                return ()
            
            final += tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])
            
        return ((query.data, final),) if len(final) > 0 else ()
            
    
    def map_using_SBERT_mapping(self,
                                queries: tuple[ActivityDefinition],
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
            self._backward_SBERT_TOs: dict = {}
            
            for target in list(self._source_definitions[self._mapping_type_direct].values()):
                SBERT_options: tuple[str] = get_SBERT_options(target)
                
                self._TOs_prepared += SBERT_options
                self._backward_SBERT_TOs |= {o: target.ID for o in SBERT_options}
                
            self._encoded_TOs = model.encode(self._TOs_prepared, convert_to_tensor = True)
                
        if self._TOs_prepared == ():
            return ()
        
        _FROMs_prepared: tuple = ()
        _backward_SBERT_FROMs: dict = {}
        
        for source in queries:
            SBERT_options: tuple[str] = get_SBERT_options(source)
            _FROMs_prepared += SBERT_options
            _backward_SBERT_FROMs |= {o: source for o in SBERT_options}
        
        if len(_FROMs_prepared) == 0:
            return ()
        
        _encoded_FROMs = model.encode(_FROMs_prepared, convert_to_tensor = True)
        
        # Compute cosine-similarities
        cosine_scores = util.cos_sim(_encoded_FROMs, self._encoded_TOs)
    
        # Loop through each item from 'items_to_map' and extract the elements that were mapped to it with its respective cosine score
        for idx, scores_tensor in enumerate(cosine_scores):
            
            # Extract the scores (values) and its respective location (indice)
            values, indices = torch.sort(scores_tensor, descending = True)
            
            # Add the n (max_number) mapped items with the highest cosine score to the list
            for ranking, value, indice in zip(reversed(range(1, n + 1)), values[0:n], indices[0:n]):
                
                if value < cutoff:
                    continue

                source: ActivityDefinition = _backward_SBERT_FROMs[_FROMs_prepared[idx]]
                target: ActivityDefinition = self._source_definitions[self._mapping_type_direct][self._backward_SBERT_TOs[self._TOs_prepared[indice]]]
                
                self._add_to_mapping(mapping_type = self._mapping_type_sbert,
                                     source = source,
                                     target = target,
                                     multiplier = float(1)
                                     )
        
        final: tuple = ()
        for query in queries:
            
            founds: tuple[tuple[ActivityDefinition, Multiplier]] = self._map(query = query,
                                                                             mapping_type = self._mapping_type_sbert,
                                                                             rules = self._rule_fns_sbert,
                                                                             multipliers_need_to_sum_to_1 = True
                                                                             )
            for query_final, multiplier_final in founds:
                
                final_found: tuple[tuple[dict, Multiplier]] = self._map(query = query_final,
                                                                        mapping_type = self._mapping_type_direct,
                                                                        rules = self._rule_fns_direct,
                                                                        multipliers_need_to_sum_to_1 = False,
                                                                        )
                if final_found == ():
                    return ()
                
                final += ((query.data, tuple([(dct, mult.multiplier * multiplier_final.multiplier) for dct, mult in final_found])),)
        
            
        return final


    def _add_to_mapping(self,
                        mapping_type: str,
                        source: ActivityDefinition,
                        target: (ActivityDefinition | dict),
                        multiplier: (float | None)) -> None:
        
        if mapping_type not in self._source_definitions:
            self._source_definitions[mapping_type]: dict = {}
            
        if mapping_type not in self._target_definitions:
            self._target_definitions[mapping_type]: dict = {}
        
        if source.ID not in self._source_definitions[mapping_type]:
            self._source_definitions[mapping_type][source.ID]: ActivityDefinition = source
            self._target_definitions[mapping_type][source.ID]: tuple[tuple[(ActivityDefinition | dict), Multiplier]] = ((target, Multiplier(multiplier = multiplier)),)
            
        else:
            self._target_definitions[mapping_type][source.ID] += ((target, Multiplier(multiplier = multiplier)),)
        
        # Since we add a new item, we need to reset the mapping dictionaries
        self._mappings_dict[mapping_type]: dict = {}
        self._mappings_dict_all: dict = {}



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
            
            source: ActivityDefinition = self._source_definitions[mapping_type][source_ID]
            targets: tuple[tuple[ActivityDefinition, Multiplier]] = self._target_definitions[mapping_type][source_ID]
            rule_tuples: tuple = rule_fn(source)
            
            for rule_tuple in rule_tuples:
                if not any([n is None for n in rule_tuple]) and len(rule_tuple) > 0:
                    self._mappings_dict[mapping_type][rule][rule_tuple] = targets
        
        return self._mappings_dict[mapping_type][rule]
    
    
    
    def _get_mapping_dict_all(self, mapping_type: str) -> dict:
        
        if mapping_type in self._mappings_dict_all:
            return self._mappings_dict_all[mapping_type]
        else:
            self._mappings_dict_all[mapping_type]: dict = {}
        
        if mapping_type not in self._mappings_dict:
            return {}
        
        for rule, elements in self._mappings_dict[mapping_type].items():
            for rule_tuple, targets in elements.items():
                
                if rule_tuple in self._mappings_dict_all[mapping_type]:
                    continue
                
                self._mappings_dict_all[mapping_type][rule_tuple] = targets
                
        return self._mappings_dict_all[mapping_type]
        
        
    

    def _map(self,
             query: ActivityDefinition,
             mapping_type: str,
             rules: tuple[str],
             multipliers_need_to_sum_to_1: bool,
             ) -> tuple[tuple[ActivityDefinition | dict, Multiplier]]:
                
        for rule in rules:
            mapping: dict = self._get_mapping_dict(mapping_type = mapping_type, rule = rule)
            found: tuple[tuple[ActivityDefinition, Multiplier]] = self._get_targets(query = query, rule = rule, mapping = mapping)
            
            if len(found) > 0:
                
                if multipliers_need_to_sum_to_1:
                    multipliers: list[float] = [m[1].multiplier for m in found]
                    
                    if multipliers == [] or sum(multipliers) < 0.999 or sum(multipliers) > 1.001:
                        continue

                return found
        
        mapping_all: dict = self._get_mapping_dict_all(mapping_type = mapping_type)
        
        for rule in rules:
            found: tuple[tuple[ActivityDefinition, Multiplier]] = self._get_targets(query = query, rule = rule, mapping = mapping_all)
            
            if len(found) > 0:
                
                if multipliers_need_to_sum_to_1:
                    multipliers: list[float] = [m[1].multiplier for m in found]
                    
                    if multipliers == [] or sum(multipliers) < 0.999 or sum(multipliers) > 1.001:
                        continue

                return found
            
        return ()
        

    def _get_targets(self, query: ActivityDefinition, rule: str, mapping: dict) -> tuple[tuple[ActivityDefinition | dict, Multiplier]]:
        rule_fn = self._rule_fns[rule]
        retrieved: list = [mapping[m] for m in rule_fn(query) if m in mapping]
        return retrieved[0] if len(retrieved) > 0 else ()

 

if __name__ == "__main__":
    
    ah: ActivityHarmonization = ActivityHarmonization(# model = "Cut-off",
                                                      # system = "Unit"
                                                      )
    
    custom_FROM_1 = ActivityDefinition(activity_code = None,
                                       reference_product_code = None,
                                       activity_name = None,
                                       name = "Product A",
                                       unit = "kilogram",
                                       location = "CH"
                                       )
    
    custom_TO_1 = ActivityDefinition(activity_code = "actcodexxx",
                                     reference_product_code = "refcode0.25",
                                     activity_name = None,
                                     name = "Product B",
                                     unit = "ton",
                                     location = None
                                     )
    
    custom_multiplier_1 = 0.001
    
    corr_FROM_1 = ActivityDefinition(activity_code = "actcode1",
                                     reference_product_code = "refcode1",
                                     activity_name = "actname1",
                                     reference_product_name = "refname1",
                                     unit = "kilogram",
                                     location = "CH"
                                     )
    
    # print(FROM_1.data)
    
    corr_TO_11 = ActivityDefinition(activity_code = "actcodexxx",
                                    reference_product_code = "refcode0.25",
                                    unit = "meter"
                                    )
        
    corr_multiplier_11 = 0.25
    
    corr_TO_12 = ActivityDefinition(activity_code = "actcode0.75",
                                    reference_product_code = "refcode0.75",
                                    activity_name = "new_name",
                                    unit = "ton"
                                    )
    corr_multiplier_12 = 0.75
    
    
    to_map_FROM_11 = ActivityDefinition(activity_code = "actcodexxx",
                                        reference_product_code = "refcode0.25",
                                        name = "Product A",
                                        unit = "kilogram",
                                        location = "CH")
    
    to_map_FROM_12 = ActivityDefinition(activity_code = "actcode0.75",
                                        reference_product_code = "refcode0.75",
                                        unit = "kilogram")
    
    to_map_TO_11_1 = {"worked": "right"}
    to_map_TO_11_2 = {"also": "here"}
    to_map_TO_12_1 = {"and finally": 1}
    
    
    query_1 = ActivityDefinition(activity_code = "actcode0.75",
                                 reference_product_code = "refcode0.75",
                                 activity_name = "actname11",
                                 reference_product_name = "refname1",
                                 unit = "kilogram",
                                 location = "CH")
    
    query_2 = ActivityDefinition(activity_code = "actcode1",
                                 reference_product_code = "refcode1",
                                 activity_name = "actname11",
                                 reference_product_name = "refname1",
                                 unit = "kilogram",
                                 location = "CH")
    
    query_3 = ActivityDefinition(activity_code = "actcode1",
                                 reference_product_code = "refcode1",
                                 activity_name = "actname11",
                                 name = "Product A",
                                 unit = "kilogram",
                                 location = "CH")
    
    query_4 = ActivityDefinition(activity_code = "actcode1",
                                 reference_product_code = "refcode1",
                                 activity_name = "actname11",
                                 name = "Product AA",
                                 unit = "kilogram",
                                 location = "CH")
    
    query_not_working = ActivityDefinition(activity_code = "xxxxx",
                                     reference_product_code = "xxxxxx",
                                     activity_name = "xxxx1",
                                     name = "Pxxxxx",
                                     unit = "xxxxxm",
                                     location = "xxxxxx")
    
    ah.add_to_custom_mapping(source = custom_FROM_1, target = custom_TO_1, multiplier = custom_multiplier_1)
    ah.add_to_correspondence_mapping(source = corr_FROM_1, target = corr_TO_11, multiplier = corr_multiplier_11)
    ah.add_to_correspondence_mapping(source = corr_FROM_1, target = corr_TO_12, multiplier = corr_multiplier_12)
    ah.add_TO(source = to_map_FROM_11, target = to_map_TO_11_1, multiplier = 0.48)
    ah.add_TO(source = to_map_FROM_11, target = to_map_TO_11_2, multiplier = 0.52)
    ah.add_TO(source = to_map_FROM_12, target = to_map_TO_12_1, multiplier = 1)

    # ah._get_mapping_dict(mapping_type = "correspondence", rule = "direct_on_actname_refname_location_unit")
    # aaa = ah._mappings_dict
    # for fn, mapping in aaa["correspondence"].items():
    #     for ID, tpl in mapping.items():
    #         for actdef, mult in tpl:
    #             print(mult.multiplier)
    
    result_1: tuple[tuple[dict, float]] = ah.map_directly(query = query_1)
    result_2: tuple[tuple[dict, float]] = ah.map_using_correspondence_mapping(query = query_2)
    result_3: tuple[tuple[dict, float]] = ah.map_using_custom_mapping(query = query_3)
    result_4: tuple[tuple[dict, float]] = ah.map_using_SBERT_mapping(queries = [query_4])
    
    result_11: tuple[tuple[dict, float]] = ah.map_directly(query = query_not_working)
    result_22: tuple[tuple[dict, float]] = ah.map_using_correspondence_mapping(query = query_not_working)
    result_33: tuple[tuple[dict, float]] = ah.map_using_custom_mapping(query = query_not_working)
    result_44: tuple[tuple[dict, float]] = ah.map_using_SBERT_mapping(queries = [query_not_working])
    
    
    
