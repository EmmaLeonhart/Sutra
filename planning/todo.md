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
