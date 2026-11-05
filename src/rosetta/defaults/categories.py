SIMAPRO_BIO_SUBCATEGORIES_MAPPING: dict = {
    "groundwater": "ground-",
    "groundwater, long-term": "ground-, long-term",
    "high. pop.": "urban air close to ground",
    "low. pop.": "non-urban air or from high stacks",
    "low. pop., long-term": "low population density, long-term",
    "stratosphere + troposphere": "lower stratosphere + upper troposphere",
    "river": "surface water",
    "river, long-term": "surface water, long-term", # CHANGED, originally, the value was 'surface water'
    "lake": "lake", # CHANGED, the value was 'surface water'
}

SIMAPRO_BIO_TOPCATEGORIES_LCI_MAPPING: dict = {
    # LCI files
    "Economic issues": "economic",
    "Emissions to air": "air",
    "Emissions to soil": "soil",
    "Emissions to water": "water",
    "Non material emissions": "non-material",
    "Non mat.": "non-material",
    "Resources": "natural resource",
    "Social issues": "social"}

SIMAPRO_BIO_TOPCATEGORIES_LCIA_MAPPING: dict = {
    # LCIA files
    "Economic": "economic",
    "Air": "air",
    "Soil": "soil",
    "Water": "water",
    "Raw": "natural resource",
    "Waste": "waste",
}

SIMAPRO_BIO_TOPCATEGORIES_MAPPING: dict = dict(SIMAPRO_BIO_TOPCATEGORIES_LCI_MAPPING,
                                         **SIMAPRO_BIO_TOPCATEGORIES_LCIA_MAPPING)

BACKWARD_SIMAPRO_BIO_SUBCATEGORIES_MAPPING: dict = {v.lower(): k for k, v in SIMAPRO_BIO_SUBCATEGORIES_MAPPING.items()}
BACKWARD_SIMAPRO_BIO_TOPCATEGORIES_MAPPING: dict = {v.lower(): k for k, v in SIMAPRO_BIO_TOPCATEGORIES_LCI_MAPPING.items()}