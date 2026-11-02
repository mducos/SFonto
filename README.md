# SFonto

SFonto is an OWL ontology dedicated to the semantic annotation of science fiction literature. It extends the [GOLEM](https://github.com/GOLEM-lab/golem-ontology) ontology and [Erlanger-CRM](http://erlangen-crm.org/), and also draws on DUL, LRMoo, and DOLCE-Lite.

The project sits within the field of digital humanities and aims to finely model narrative elements specific to SF (novums, characters, Proppian functions, Proppian roles, etc.) in order to enable structured queries over a corpus of narratives.

## Repository structure

```
├── data/
│   └── [author]_[title]_[date]/                    # one folder per annotated narrative
│   |   └── [author]_[title]_[date].ttl             # a unique ABox for each narrative
│
├── script/
│   ├── generate_ttl/                               # one python script to generate the unique ABox for each narrative
│   |   └── metadata_module.py
│   ├── query.py                                    # run SPARQL queries over the ttl files
│   └── ttl2gexf.py                                 # convert ttl files to GEXF / GraphML (Gephi visualization)
│
└── src/
|   ├── annotation_guide.docx                       # annotation guide
|   ├── CQs.xlsx                                    # competency questions (CQs) and their associated SPARQL queries
|   ├── SFonto.ttl                                  # complete ttl file of the ontology
|   ├── personality_lexicon_English_version.xlsx    # spreadsheet for the personality module
|   └── module_schemas/
|   |   ├── [module]_module.png                     # schema for each module of the ontology
|   |   └── [module]_module_example.png             # annotation example for each module
```

### `data/`
Each subfolder corresponds to a narrative in the corpus and contains:
- a facultative annotation file produced according to the annotation guide (`src/annotation_guide.docx`);
- the ABox in Turtle format (`.ttl`), conforming to the SFonto ontology.

### `script/`

* `query.py`: script for querying the `.ttl` files (a single narrative's data or the full ontology) using SPARQL queries, in particular those defined in `src/CQs.xlsx`.

* `ttl2gexf.py`: script converting `.ttl` files to `.gexf` and `.graphml`, for network visualization and analysis (e.g. with Gephi).

### `src/`

* `annotation_guide.docx`: methodology and conventions followed when annotating narratives.

* `CQs.xlsx`: list of questions the ontology should be able to answer, each paired with its corresponding SPARQL query.

* `SFonto.ttl`: the full ontology file (classes, properties, reference individuals).

* `personality_lexicon_English_version.xlsx`: Excel file documenting personality traits dedicated to characters' personality traits.

* `module_schemas/`: for each module of the ontology, a schema and an example illustrating its use.

## Citing this work

XXX
