# Référence Python

Les fonctions de l'API, écrites une fois et utilisées par les vues, les serializers, l'admin Django et les tâches
Celery. Elles sont documentées à partir de leurs **docstrings** : cette référence est générée, elle ne peut donc
pas s'écarter du code. Les docstrings sont en anglais.

| Module | Ce qu'il fait |
|---|---|
| [Droits et modération](rights-moderation.md) | `session_rights`, les statuts, la validation des fiches et des sessions, ce que voit le public, la publication après validation, les données de la page Review |
| [Vocabulaires](vocabularies.md) | Termes d'ontologie vérifiés à leur source (EBI OLS, ROR) |
| [Fichiers et dépôts](files-repositories.md) | Envois, dépôt dans Zenodo, description d'une notice, vérification des liens, outils de détection |
| [Jeux de données](datasets.md) | Export et import des métadonnées d'un jeu de données |
| [Comptes](accounts.md) | Inscription, domaines d'e-mail, preuve ORCID, e-mails |
| [Tâches et utilitaires](tasks.md) | Les tâches Celery, les signaux, les mises à niveau des données |

!!! tip "Vous cherchez une règle plutôt qu'une fonction ?"
    Les droits de chaque rôle sont dans [Droits et statuts](../rights.md) ; les routes HTTP dans l'
    [API REST](../api/index.md).

## Conventions

- Les docstrings sont en anglais et suivent le style Google (`Args:`, `Returns:`, `Raises:`) quand une fonction a
  des paramètres qui méritent d'être nommés.
- Une fonction dont le nom commence par `_` est interne et n'est pas listée.
- Lancez `mkdocs serve` pour lire cette référence en local (voir [Contribuer](../contributing.md)).
