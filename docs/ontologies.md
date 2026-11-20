# Vocabularies (ontologies)

Some fields point to a term of a controlled vocabulary next to their free text. The term is
checked at its source (EBI Ontology Lookup Service, ROR registry) before it is stored.

| Field | Vocabulary |
|---|---|
| Species | NCBI Taxonomy |
| Strain | Experimental Factor Ontology (EFO) for mice, e.g. C57BL/6J `EFO:0000606`; Rat Strain Ontology (RS) for rats (`&ontology=rs` in the search) |
| Sex of an animal profile | PATO (filled from male / female) |
| Developmental stage | Mouse Developmental Stages (MmusDv) for mice; generic stages of Uberon for other species (filled from pup / juvenile / adult) |
| Treatment compound | ChEBI |
| Diet of an animal profile | Experimental Factor Ontology (EFO) |
| Behaviors of a session | Neuro Behavior Ontology (NBO) |
| Organization of a laboratory | ROR registry |

A **strain chosen in the ontology** is what the ontology says: it is created already *validated* (the term was checked at its source), its genetic background is the label of the term and it has no bibliography to write. There is **one strain per term**: asking for a term that already has a strain gives that strain (and validates it if it was not), and a term cannot be given to a second strain. A strain written by hand still needs its genetic background and is reviewed like the other entries.

`GET /api/ontology/search/?field=<field>&q=<text>` (signed-in users, 60/min) feeds the
autocomplete. The units of the numeric fields are documented with the Units Ontology
(hertz `UO:0000106`, second `UO:0000010`, degree Celsius `UO:0000027`, lux `UO:0000116`).
