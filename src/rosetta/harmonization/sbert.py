"""Sentence-BERT (SBERT) helpers for fuzzy matching of names."""

import pathlib

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util

from .. import _helpers as hp
from .._paths import SBERT_MODEL_DIR, SBERT_MODEL_NAME


def load_sbert_model(path: pathlib.Path | str | None = SBERT_MODEL_DIR, device: str | None = None) -> SentenceTransformer:
    """Load the SBERT model from ``path`` if it exists, otherwise download 'all-MiniLM-L6-v2'."""
    kwargs: dict = {} if device is None else {"device": device}
    if path is not None and pathlib.Path(path).exists():
        return SentenceTransformer(str(path), **kwargs)
    return SentenceTransformer(SBERT_MODEL_NAME, **kwargs)


def default_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def map_using_SBERT(items_to_map: tuple, items_to_map_to: tuple, max_number: int = 1) -> pd.DataFrame:
    
    # Check function input type
    hp.check_function_input_type(map_using_SBERT, locals())
    
    # Raise error if max number is lower than 1
    if max_number < 1:
        raise ValueError("'max_number' argument needs to be greater or equal than 1 but currently is '{}'".format(max_number))
    
    model = load_sbert_model()

    # Compute embedding for both lists
    embeddings1 = model.encode(items_to_map, convert_to_tensor = True)
    embeddings2 = model.encode(items_to_map_to, convert_to_tensor = True)

    # Compute cosine-similarities
    cosine_scores = util.cos_sim(embeddings1, embeddings2)

    # Initialize variable
    data: list = []

    # Loop through each item from 'items_to_map' and extract the elements that were mapped to it with its respective cosine score
    for idx_I, scores_tensor in enumerate(cosine_scores):
        
        # Extract the scores (values) and its respective location (indice)
        values, indices = torch.sort(scores_tensor, descending = True)
        
        # Add the n (max_number) mapped items with the highest cosine score to the list
        data += [{"orig": items_to_map[idx_I],
                  "mapped": items_to_map_to[indice],
                  "score": float(value),
                  "ranking": idx} for idx, value, indice in zip(reversed(range(1, max_number + 1)), values[0:max_number], indices[0:max_number])]

    return pd.DataFrame(data)
