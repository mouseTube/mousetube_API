---
hide:
  - navigation
  - toc
---

# Database schema

The tables of the API, with every field described in its card. Touch or hover a table to isolate its links;
use the list to jump to a table. The colour of a card is its family (accounts, vocabularies, animals,
protocol and equipment, session, files and repository).

<iframe class="mt-schema" src="../../assets/schema/index.html?lang=en"
        title="mouseTube database schema (interactive)" loading="lazy"></iframe>

[Open the schema full screen](../assets/schema/index.html?lang=en){ .md-button target="_blank" }

## Reading the schema

- **The recording session is the centre.** It gathers a protocol, a laboratory, animal profiles, equipment
  (software versions and hardware) and references, and its files. It is what gets published.
- **Entries are shared by everybody.** Hardware, software, laboratories, strains and animal profiles are
  catalog entries: one entry can be used by the sessions of many people, which is why a *validated* entry is
  locked (see [Rights and statuses](rights.md)).
- **Vocabulary terms sit next to the free text.** A field such as `sex` keeps its free value, and `sex_term`
  points to the term of an ontology checked at its source (`OntologyTerm`).
- **Deleting.** Each link says what happens when its target disappears: `CASCADE` deletes the row with it,
  `SET NULL` keeps the row and empties the link.
- **Every entry has `created_by`** (the author, `User`) and its dates. These links are not drawn.

!!! note "The page follows the models"
    A test (`test_docs_schema.py`) fails when a table or a field of `models.py` is added, renamed or removed
    without the page. The data is in `docs/assets/schema/schema-<lang>.json`; edit the English and the French
    files together.

## Statuses used by the tables

| Table | `status` values |
|---|---|
| Laboratory, Contact, Reference, Software, Hardware, Strain, AnimalProfile | `draft`, `waiting validation`, `validated` |
| Protocol | always `validated` (its name is a code) |
| Study | stays `draft` (private, not reviewed) |
| RecordingSession | `draft`, `waiting validation`, `shared`, `published` |
| File | processing: `pending`, `processing`, `done`, `error` |
