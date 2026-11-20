---
hide:
  - navigation
  - toc
---

# Schéma de la base de données

Les tables de l'API, avec chaque champ décrit dans sa carte. Touchez ou survolez une table pour isoler ses
liaisons ; la liste permet d'aller à une table. La couleur d'une carte est sa famille (comptes, vocabulaires,
animaux, protocole et matériel, session, fichiers et dépôt).

<iframe class="mt-schema" src="../../../assets/schema/index.html?lang=fr"
        title="Schéma de la base mouseTube (interactif)" loading="lazy"></iframe>

[Ouvrir le schéma en plein écran](../assets/schema/index.html?lang=fr){ .md-button target="_blank" }

## Lire le schéma

- **La session d'enregistrement est le centre.** Elle rassemble un protocole, un laboratoire, des profils
  d'animaux, le matériel (versions de logiciels et matériel) et des références, ainsi que ses fichiers. C'est
  elle qui est publiée.
- **Les fiches sont partagées par tous.** Matériel, logiciels, laboratoires, souches et profils d'animaux sont
  des fiches de catalogue : une même fiche peut servir aux sessions de plusieurs personnes, c'est pourquoi une
  fiche *validée* est verrouillée (voir [Droits et statuts](rights.md)).
- **Les termes de vocabulaire sont à côté du texte libre.** Un champ comme `sex` garde sa valeur libre, et
  `sex_term` pointe vers le terme d'une ontologie vérifié à la source (`OntologyTerm`).
- **Suppression.** Chaque liaison dit ce qui se passe quand sa cible disparaît : `CASCADE` supprime la ligne
  avec elle, `SET NULL` garde la ligne et vide la liaison.
- **Chaque fiche a un `created_by`** (l'auteur, `User`) et ses dates. Ces liaisons ne sont pas tracées.

!!! note "La page suit les modèles"
    Un test (`test_docs_schema.py`) échoue quand une table ou un champ de `models.py` est ajouté, renommé ou
    supprimé sans la page. Les données sont dans `docs/assets/schema/schema-<lang>.json` ; modifiez les
    fichiers anglais et français ensemble.

## Statuts utilisés par les tables

| Table | Valeurs de `status` |
|---|---|
| Laboratory, Contact, Reference, Software, Hardware, Strain, AnimalProfile | `draft`, `waiting validation`, `validated` |
| Protocol | toujours `validated` (son nom est un code) |
| Study | reste `draft` (privée, non relue) |
| RecordingSession | `draft`, `waiting validation`, `shared`, `published` |
| File | traitement : `pending`, `processing`, `done`, `error` |
