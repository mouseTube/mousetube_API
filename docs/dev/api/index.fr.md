# API REST

mouseTube est une **API REST JSON** (Django REST framework). Le site n'est qu'un de ses clients : tout ce que
vous pouvez faire sur le site, vous pouvez le faire depuis un script.

| | |
|---|---|
| **URL de base** | `https://<votre mouseTube>/api/` (en local `http://localhost:8000/api/`) |
| **Documentation interactive (Swagger)** | `/swagger/` sur le même hôte : essayez chaque route dans le navigateur |
| **Schéma OpenAPI** | `/schema/` (YAML), pour générer un client |
| **Format** | JSON en entrée, JSON en sortie. Les fichiers sont envoyés en `multipart/form-data`. |
| **Version de l'API** | `GET /api/version/` |

!!! tip "Swagger ou cette page ?"
    Swagger liste **chaque route et chaque champ**, toujours à jour. Ces pages ajoutent ce qu'il ne dit pas :
    **quoi appeler pour atteindre un but** ([Recettes](recipes.md)), **qui y est autorisé**
    ([Droits et statuts](../rights.md)) et l'ordre des étapes (décrire, ajouter des fichiers, partager, publier).

## Authentification

Lire les données publiques ne demande **aucun jeton**. Tout le reste demande un **jeton d'accès JWT**, envoyé dans
un en-tête :

```http
Authorization: Bearer <jeton d'accès>
```

=== "Obtenir un jeton (curl)"

    ```bash
    curl -s -X POST "$HOST/auth/jwt/create/" \
         -H "Content-Type: application/json" \
         -d '{"username": "alice", "password": "…"}'
    # {"refresh": "eyJ…", "access": "eyJ…"}
    ```

=== "Python"

    ```python
    import requests

    HOST = "http://localhost:8000"  # sans /api : /auth/ est à côté de /api/
    tokens = requests.post(
        f"{HOST}/auth/jwt/create/", json={"username": "alice", "password": "…"}
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access']}"}
    ```

- Le **jeton d'accès dure une heure**. Renouvelez-le avec `POST /auth/jwt/refresh/` et `{"refresh": "…"}` ; le
  jeton de rafraîchissement dure sept jours.
- Sur le site, **Account → API token** montre le jeton d'accès de votre session, pour un essai rapide.
- `GET /auth/users/me/` répond qui vous êtes (`id`, `username`, `is_staff`…).
- Un compte **pas encore actif** (e-mail non confirmé, ou non accepté par un administrateur) reçoit un **401**
  avec `account_status` : `awaiting_email_confirmation` ou `awaiting_review`.
- L'inscription est `POST /auth/users/` (une adresse e-mail **institutionnelle** est exigée), puis l'utilisateur
  confirme l'e-mail et un administrateur active le compte. Voir [Demandes de compte](../accounts.md).

!!! warning "Jeton = vous"
    Quiconque a votre jeton agit comme vous. Gardez-le hors du code que d'autres peuvent lire.

## Conventions

### Pagination

Les listes sont paginées : `?page=2&page_size=20` (10 par défaut, 100 au plus).

```json
{ "count": 1620, "next": "…/api/file/?page=2&page_size=1", "previous": null, "results": [ … ] }
```

Certaines listes courtes (dépôts, espèces utilisées par un formulaire…) répondent un simple tableau : Swagger dit
lesquelles.

### Recherche, filtres, tri

`?search=` regarde dans les champs texte de l'objet et de ce vers quoi il pointe ; plusieurs mots doivent tous être
trouvés. Les filtres portent le nom de ce qu'ils veulent dire (`species`, `sex`, `age`, `file_format`,
`repository`, `type`, `status`…). Chaque liste dit lesquels dans Swagger et dans les [recettes](recipes.md).

### Statuts et visibilité

Les listes montrent **ce que vous pouvez voir** : les fiches validées et les vôtres. Un objet privé à quelqu'un
d'autre est **404**, pas 403. Voir [Droits et statuts](../rights.md).

### Erreurs

| Code | Sens | Corps |
|---|---|---|
| **400** | Les données ne sont pas valides | `{"champ": ["message"]}` ou `{"non_field_errors": […]}` |
| **401** | Jeton absent ou invalide, ou compte inactif | `{"detail": "…"}` |
| **403** | Vous pouvez le voir mais pas le faire | `{"detail": "…"}` |
| **404** | N'existe pas, ou est privé à quelqu'un d'autre | `{"detail": "…"}` |
| **409** | L'état l'interdit (rien de nouveau à publier, fiches en attente de validation…) | `{"detail": "…"}` |
| **413** | Le fichier est trop gros | `{"error": "…", "limit": octets}` |
| **429** | Trop de requêtes (limite de débit) | `{"detail": "…"}` |

!!! info "Limites de débit"
    Par adresse : connexions et demandes de jeton 10 par minute, inscriptions 20 par heure, recherche de termes de
    vocabulaire 60 par minute. Un script qui reçoit un 429 doit attendre.

## Ressources principales

| Ressource | Route | Lecture | Écriture |
|---|---|---|---|
| Fichiers (vocalisations) | `/api/file/` | tout le monde (sessions publiques) | auteur |
| Sessions d'enregistrement | `/api/recording-session/` | leur auteur | leur auteur |
| Protocoles | `/api/protocol/` | validés + les siens | tout utilisateur (validé d'office) |
| Profils d'animaux, souches, espèces | `/api/animalprofile/`, `/api/strain/`, `/api/species/` | validés + les siens | tout utilisateur (espèces : administrateurs) |
| Matériel, logiciels | `/api/hardware/`, `/api/software/` | validés + les siens | tout utilisateur |
| Laboratoires, références, contacts | `/api/laboratory/`, `/api/reference/`, `/api/contact/` | validés + les siens | tout utilisateur |
| Études | `/api/study/` | leur auteur | leur auteur |
| Jeux de données | `/api/dataset/` | tout le monde | administrateurs |
| Dépôts | `/api/repository/` | tout le monde | admin Django |
| Résultats de détection (USV) | `/api/file/<id>/usv-detections/`, `/api/usv-detection/<id>/` | fichiers publics | auteur du fichier |
| Relecture (administrateurs) | `/api/review/…` | administrateurs | administrateurs |
| Recherche de vocabulaire | `/api/ontology/search/` | connecté | |

Suite : [Recettes](recipes.md).
