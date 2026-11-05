# rosetta
The "rosetta" repository is a collection of useful functions to work with SimaPro data in Brightway.

The repository provides several modules that contain functions for different purposes:
- [lci.py](src/rosetta/lci.py) contains functions to import and harmonize life cycle inventory data from either SimaPro or XML (ecospold2) data
- [lcia.py](src/rosetta/lcia.py) contains functions to import life cycle impact assessment methods from either SimaPro or Excel and construct a respective biosphere out of it.
- [link.py](src/rosetta/link.py) contains functions to facilitate linking, either internally (within a database) or externally (to another database). It also provides a function to remove the existing linking.
- [exporter.py](src/rosetta/exporter.py) provides a function to export a registered Brightway activity back to a SimaPro CSV. Note: the export only works if data has been imported with [lci.py](src/rosetta/lci.py) and follows SimaPro nomenclature.
- [calculation.py](src/rosetta/calculation.py) provides a class to facilitate LCA calculation. Apart from only basic scores calculation, it is possible to easily calculate process or emission contribution, extract characterization factors or the exchanges of a life cycle inventory with this class.
- [harmonization.py](src/rosetta/harmonization.py) provides functions to either map flows between two biospheres (e.g. biosphere from SimaPro and XML) or to map activities/exchanges from one database to another (e.g. from ecoinvent v3.8 to v3.10).
- [correspondence.py](src/rosetta/correspondence/correspondence.py) provides functions to create a mapping between activities from different ecoinvent database versions.
- [builder.py](src/rosetta/builder.py) ensures to create standardized activities and exchanges that can then be used for registering in the Brightway background. 

Check out the [notebook folder](notebook/) for specific use cases.

## Installation
rosetta is an installable Python package (`src/rosetta`). The Brightway2 / PyTorch stack is easiest to install with conda, then rosetta itself with pip:

```bash
conda env create -f environment_macos.yml   # or: bw2_ab_environment.yml on Linux
conda activate rosetta
pip install -e .                            # editable install from the repository root
```

Usage:

```python
import rosetta
from rosetta.lci import import_SimaPro_LCI_inventories
from rosetta.lcia import import_SimaPro_LCIA_methods
from rosetta.calculation import LCA_Calculation
from rosetta.correspondence.correspondence import Correspondence
```

Input data (SimaPro exports, ecoinvent correspondence files) goes into `data/lci`, `data/lcia` and `data/correspondence`.

`lci.set_code` keeps a registry of generated codes in `UUIDs.xlsx` next to the module. Set the environment variable `ROSETTA_UUID_FILE` to store it elsewhere.

## Dependencies
This repository depends on the Brightway v2 package and contains functions to facilitate the work with SimaPro LCI and LCIA data. The package is not yet compatible with Brightway2.5, but will so in the future.
The package works with the following packages:
- bw2io → _v0.8.12_
- bw2data → _v3.6.6_
- bw2calc → _v1.8.2_
- bw2analyzer → _v0.10_
- sentence-transformers → _v2.7.0_
