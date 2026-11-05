"""Locations of files shipped with or written by rosetta."""

import os
import pathlib

PACKAGE_DIR: pathlib.Path = pathlib.Path(__file__).parent
DEFAULTS_DIR: pathlib.Path = PACKAGE_DIR / "defaults"
CAS_FILE: pathlib.Path = DEFAULTS_DIR / "CAS.json"

# Optional local copy of the SBERT model; downloaded from Hugging Face if missing
SBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"
SBERT_MODEL_DIR: pathlib.Path = DEFAULTS_DIR / SBERT_MODEL_NAME


def uuid_registry_file() -> pathlib.Path:
    """Excel file in which generated inventory codes are registered.

    Defaults to 'UUIDs.xlsx' inside the package; override with the environment variable 'ROSETTA_UUID_FILE'.
    """
    return pathlib.Path(os.environ.get("ROSETTA_UUID_FILE", PACKAGE_DIR / "UUIDs.xlsx"))
