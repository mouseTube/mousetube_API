# Contribuer

## Installer

Suivez le [README](https://github.com/mouseTube/mousetube_API#readme) pour lancer l'API avec Docker, et
[Configuration](configuration.md) pour le `.env`. Avec `DEBUG=true` et les réglages de la base, vous pouvez
travailler en local.

## Vérifier votre travail

```bash
python manage.py test mousetube_api.tests     # les tests (dans le conteneur web)
ruff check . && ruff format --check .         # style et lint
bandit -r mousetube_api -x mousetube_api/tests -ll   # analyse de sécurité
```

La CI lance ruff et bandit sur chaque pull request. Écrivez un test pour ce que vous ajoutez : les droits, la
validation et tout ce qui écrit des données en méritent un.

## Les migrations sont versionnées

Changez un modèle, puis :

```bash
python manage.py makemigrations
```

Relisez le fichier écrit et **committez-le**. Un test échoue quand un modèle a changé sans sa migration. Le
conteneur ne lance que `migrate`. Les conversions de lignes existantes vont dans `normalize_data`
(`utils/data_upgrades.py`, sans risque à relancer).

## Quand vous changez les règles

Les droits sont un contrat avec le site et avec ceux qui écrivent des scripts sur l'API.

- **Une nouvelle route, ou un changement de qui peut en utiliser une** : décidez d'abord sa ligne dans
  [Droits et statuts](rights.md), puis testez-la. Les catalogues sont dans `test_rights_matrix.py`, les sessions
  dans `test_session_rights.py`.
- **Une route qui montre une session ou ce qu'elle utilise** : elle doit cacher ce que personne n'a validé.
  Ajoutez-la aux routes que lit `test_public_visibility.py` avec des témoins, et le test vous dira si elle fuit.
- **Un nouveau catalogue modéré** : donnez-lui `status` et `created_by`, utilisez `visible_to` dans son queryset,
  `IsCreatorOrReadOnly` pour les modifications et le `ModerationMixin` dans son serializer, et ajoutez-le à
  `CatalogRightsTests`.

## Écrire ces pages

La documentation est un site [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) dans `docs/`,
publié sur GitHub Pages par `.github/workflows/docs.yml` quand `main` change.

```bash
pip install -r requirements-docs.txt
mkdocs serve            # http://127.0.0.1:8000 avec rechargement
mkdocs build --strict   # ce que lance la CI : un lien cassé ou une page manquante la fait échouer
```

- **Deux langues.** Une page `nom.md` est en anglais et `nom.fr.md` sa version française, côte à côte. Une page
  sans fichier français montre l'anglais. Gardez les deux à jour.
- **Le guide utilisateur** est dans `docs/user/`, la documentation développeur dans `docs/dev/`.
- **Le schéma de la base** est `docs/assets/schema/schema-en.json` et `schema-fr.json`. Quand vous changez un
  modèle, lancez `python manage.py sync_schema_docs` (il ajoute les nouvelles tables et champs, retire les anciens,
  corrige les types), puis écrivez les descriptions `TODO` dans les deux langues. Un test échoue tant que ce n'est
  pas fait.
- **La référence Python** est générée depuis les docstrings (`::: mousetube_api.utils.module`). Écrivez une
  docstring quand vous ajoutez une fonction publique ; utilisez `Args:` / `Returns:` quand les paramètres demandent
  à être nommés.
- **Les captures d'écran** sont dans `docs/assets/img/` (PNG, environ 1200 px de large). Donnez à chacune un texte
  `alt` utile.
- **Accessibilité.** Un seul titre `#` par page, des titres dans l'ordre, des liens qui disent où ils mènent, aucune
  information portée par la couleur seule.
