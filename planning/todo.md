# TODO

## Propositional Realization Templates (HIGH PRIORITY)

Generate canonical English sentence templates for every Wikidata property (~13,000 properties).

**Format:** `data/property_templates.json`
```json
{
  "P31": {
    "label": "instance of",
    "realizations": ["$SUB is a(n) $OBJ"]
  },
  "P17": {
    "label": "country",
    "realizations": ["$SUB is in $OBJ", "$SUB is located in $OBJ"]
  },
  "P279": {
    "label": "subclass of",
    "realizations": ["$SUB is a type of $OBJ", "$SUB is a subclass of $OBJ"]
  }
}
```

**Steps:**
1. Fetch all ~13,000 Wikidata properties with their English labels and descriptions
2. Generate canonical sentence templates with $SUB and $OBJ slots
3. For each triple in our data, fill slots with English labels to create propositional strings
4. Embed each realized proposition
5. Create geodesics for propositional embeddings (these CAN connect to the property embedding since they are linguistic)

**Why this matters:**
- Turns structural triples into natural language propositions
- Enables propositional geodesics (currently not possible because properties aren't linguistic endpoints)
- Tests whether embedding geometry encodes logical relations when expressed as full sentences
- Connects to redoing-paper finding: "subject axis contributes 3.5x more to similarity than predicate axis" — propositional form may change this

**Future:** Extend templates to other languages.

**Status:** `data/properties.json` now has all 13,286 properties with simple `"$SUB {label} $OBJ"` realizations (37,252 total). LLM-generated natural phrasings in progress via `generate_property_templates.py`.

## Monthly Property Scanner (GitHub Actions)

Wikidata creates new properties regularly. Set up a GitHub Actions workflow that runs once a month to:

1. Fetch all current Wikidata property IDs
2. Diff against `data/properties.json`
3. For any new properties, fetch their English labels and aliases
4. Add them to `data/properties.json` with `"$SUB {label} $OBJ"` realizations
5. Auto-commit and push

This keeps the property list current without manual intervention. Could be as simple as running `fetch_all_properties.py` with a merge-not-overwrite mode.
