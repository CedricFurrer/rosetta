# Exact names of compartments in CSV files from SimaPro
SIMAPRO_PRODUCT_COMPARTMENTS: dict = {"products": "Products"}

SIMAPRO_SUBSTITUTION_COMPARTMENTS: dict = {"avoided_products": "Avoided products"}

SIMAPRO_TECHNOSPHERE_COMPARTMENTS: dict = {"materials_fuels": "Materials/fuels",
                                           "electricity_heat": "Electricity/heat",
                                           "final_waste_flows": "Final waste flows",
                                           "waste_to_treatment": "Waste to treatment"}

SIMAPRO_BIOSPHERE_COMPARTMENTS: dict = {"resources": "Resources",
                                        "emissions_air": "Emissions to air",
                                        "emissions_water": "Emissions to water",
                                        "emissions_soil": "Emissions to soil",
                                        "non_material_emissions": "Non material emissions",
                                        "social_issues": "Social issues",
                                        "economic_issues": "Economic issues"}

SIMAPRO_COMPARTMENTS: dict = dict(**SIMAPRO_PRODUCT_COMPARTMENTS,
                                  **SIMAPRO_SUBSTITUTION_COMPARTMENTS,
                                  **SIMAPRO_TECHNOSPHERE_COMPARTMENTS,
                                  **SIMAPRO_BIOSPHERE_COMPARTMENTS)

SIMAPRO_CATEGORY_TYPE_COMPARTMENT_MAPPING: dict = {"material": SIMAPRO_COMPARTMENTS["materials_fuels"],
                                                   "waste treatment": SIMAPRO_COMPARTMENTS["waste_to_treatment"],
                                                   "energy": SIMAPRO_COMPARTMENTS["electricity_heat"],
                                                   "processing": SIMAPRO_COMPARTMENTS["materials_fuels"],
                                                   "transport": SIMAPRO_COMPARTMENTS["materials_fuels"],
                                                   "use": SIMAPRO_COMPARTMENTS["materials_fuels"]}

SIMAPRO_COMPARTMENT_ORDER: dict = (SIMAPRO_COMPARTMENTS["products"],
                                   SIMAPRO_COMPARTMENTS["avoided_products"],
                                   SIMAPRO_COMPARTMENTS["resources"],
                                   SIMAPRO_COMPARTMENTS["materials_fuels"],
                                   SIMAPRO_COMPARTMENTS["electricity_heat"],
                                   SIMAPRO_COMPARTMENTS["emissions_air"],
                                   SIMAPRO_COMPARTMENTS["emissions_water"],
                                   SIMAPRO_COMPARTMENTS["emissions_soil"],
                                   SIMAPRO_COMPARTMENTS["final_waste_flows"],
                                   SIMAPRO_COMPARTMENTS["non_material_emissions"],
                                   SIMAPRO_COMPARTMENTS["social_issues"],
                                   SIMAPRO_COMPARTMENTS["economic_issues"],
                                   SIMAPRO_COMPARTMENTS["waste_to_treatment"])