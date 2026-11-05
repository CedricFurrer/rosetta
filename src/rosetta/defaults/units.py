import bw2io

# Add custom normalizations
additional_normalization_mapping: dict = {"guest night": "day"}
additional_transformation_mapping: list[tuple] = [("km*year", "meter-year", 1e3),
                                                  ]

# Create backward unit mappings
# ... import from Brightway2
unit_transformation_mapping: dict = {m[0]: {"unit_transformed": m[1], "multiplier": m[2]} for m in bw2io.units.DEFAULT_UNITS_CONVERSION + additional_transformation_mapping}
backward_unit_normalization_mapping_orig: dict = {v: k for k, v in bw2io.units.UNITS_NORMALIZATION.items()}

# Merge
backward_unit_normalization_mapping: dict = dict(**backward_unit_normalization_mapping_orig, **additional_normalization_mapping)

# import pint
# ureg = pint.UnitRegistry()
# kg_unit: str = "kg"
# kg_pint = ureg(kg_unit)

# # Define the unit "kg/ha"
# kg_per_ha = ureg.kg / ureg.hectare  # kg/ha is kilogram per hectare

# # Define the quantity in kg/ha
# quantity_kg_per_ha = 100 * kg_per_ha  # Example: 100 kg/ha

# # Convert kg/ha to kg/m²
# quantity_kg_per_m2 = quantity_kg_per_ha.to(ureg.kg / ureg.meter**2)

# # Print the result
# print(kg_per_ha)
# quantity_kg_per_ha.to(ureg.kg / ureg.l)
# print(f"{quantity_kg_per_ha} is equal to {quantity_kg_per_m2}")