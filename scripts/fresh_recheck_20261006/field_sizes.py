"""Fresh yearly field sizes from the OpenAlex API (same field definitions as the sampler)."""

import os
import sys

import pandas as pd
import requests

KEY, MAIL = os.environ["OPENALEX_API_KEY"], os.environ["OPENALEX_EMAIL"]
H = {"User-Agent": f"NeuroAI-CN-fresh/1.0 (mailto:{MAIL})"}
DEFS = {
    "neuro": "primary_topic.field.id:fields/28",
    "ai_extended": "primary_topic.subfield.id:subfields/1702|subfields/1707",
    "ai_strict": "primary_topic.subfield.id:subfields/1702",
}


def sizes(flt):
    r = requests.get(
        "https://api.openalex.org/works",
        headers=H,
        timeout=90,
        params={
            "filter": flt,
            "group_by": "publication_year",
            "per-page": 200,
            "api_key": KEY,
            "mailto": MAIL,
        },
    )
    r.raise_for_status()
    return {int(g["key"]): g["count"] for g in r.json()["group_by"]}


rows = {k: sizes(v) for k, v in DEFS.items()}
df = pd.DataFrame(rows).sort_index().loc[1990:2025]
df.index.name = "year"
df.to_csv(sys.argv[1])
print(df.tail(8))
