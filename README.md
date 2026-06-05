# rosetta
The "rosetta" repository is a collection of useful functions to work with SimaPro data in Brightway.

The repository provides several modules that contain functions for different purposes:
- [lci.py](lci.py) contains functions to import and harmonize life cycle inventory data from either SimaPro or XML (ecospold2) data
- [lcia.py](lcia.py) contains functions to import life cycle impact assessment methods from either SimaPro or Excel and construct a respective biosphere out of it.
- [link.py](link.py) contains functions to facilitate linking, either internally (within a database) or externally (to another database). It also provides a function to remove the existing linking.
- [exporter.py](exporter.py) provides a function to export a registered Brightway activity back to a SimaPro CSV. Note: the export only works if data has been imported with [lci.py](lci.py) and follows SimaPro nomenclature.
- [calculation_bw2.py](calculation_bw2.py) provides a class to facilitate LCA calculation. Apart from only basic scores calculation, it is possible to easily calculate process or emission contribution, extract characterization factors or the exchanges of a life cycle inventory with this class.
- [harmonization.py](harmonization.py) provides functions to either map flows between two biospheres (e.g. biosphere from SimaPro and XML) or to map activities/exchanges from one database to another (e.g. from ecoinvent v3.8 to v3.10).
- [correspondence.py](correspondence/correspondence.py) provides functions to create a mapping between activities from different ecoinvent database versions.
- [builder.py](builder.py) ensures to create standardized activities and exchanges that can then be used for registering in the Brightway background. 

Checkout the [notebook folder](notebook/) for specific use cases.

## Dependencies
This repository depends on the Brightway v2 package and contains functions to facilitate the work with SimaPro LCI and LCIA data. The package is not yet compatible with Brightway2.5, but will so in the future.
The package works with the following packages:
- bw2io → _v0.8.12_
- bw2data → _v3.6.6_
- bw2calc → _v1.8.2_
- bw2analyzer → _v0.10_
- sentence-transformers → _v2.7.0_
