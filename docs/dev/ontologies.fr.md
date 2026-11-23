# Vocabulaires (ontologies)

Certains champs pointent vers un terme d'un vocabulaire contrôlé à côté de leur texte libre. Le terme est vérifié à
sa source (EBI Ontology Lookup Service, registre ROR) avant d'être stocké.

| Champ | Vocabulaire |
|---|---|
| Espèce | NCBI Taxonomy |
| Souche | Experimental Factor Ontology (EFO) pour les souris, par ex. C57BL/6J `EFO:0000606` ; Rat Strain Ontology (RS) pour les rats (`&ontology=rs` dans la recherche) |
| Sexe d'un profil d'animaux | PATO (rempli depuis male / female) |
| Stade de développement | Mouse Developmental Stages (MmusDv) pour les souris ; stades génériques d'Uberon pour les autres espèces (rempli depuis pup / juvenile / adult) |
| Composé du traitement | ChEBI |
| Régime d'un profil d'animaux | Experimental Factor Ontology (EFO) |
| Comportements d'une session | Neuro Behavior Ontology (NBO) |
| Organisation d'un laboratoire | Registre ROR |

Une **souche choisie dans l'ontologie** est ce que dit l'ontologie : elle est créée déjà *validée* (le terme a été
vérifié à sa source), son fond génétique est le libellé du terme et elle n'a pas de bibliographie à écrire. Il y a
**une souche par terme** : demander un terme qui a déjà une souche donne cette souche (et la valide si elle ne
l'était pas), et un terme ne peut pas être donné à une deuxième souche. Une souche écrite à la main a encore besoin
de son fond génétique et est relue comme les autres fiches.

`GET /api/ontology/search/?field=<field>&q=<text>` (utilisateurs connectés, 60/min) alimente l'autocomplétion. Les
unités des champs numériques sont documentées avec l'Units Ontology (hertz `UO:0000106`, seconde `UO:0000010`,
degré Celsius `UO:0000027`, lux `UO:0000116`).
