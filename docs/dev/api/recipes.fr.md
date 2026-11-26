# Recettes de l'API

Quoi appeler pour atteindre un but, avec des exemples. Ils utilisent `curl` et Python (`requests`). Chaque exemple a
été exécuté sur une vraie instance.

```bash
API=http://localhost:8000/api          # votre instance, avec /api
HOST=http://localhost:8000             # la même, sans /api (pour /auth/)
```

```python
import requests

API, HOST = "http://localhost:8000/api", "http://localhost:8000"
```

!!! note "Lire sans jeton, écrire avec un jeton"
    La première partie ne demande **aucun compte**. La seconde demande un jeton : voir [Authentification](index.md#authentification).

## Lire les données

### Lister les enregistrements

Chaque fichier d'une session publique. Paginez avec `page` et `page_size` (100 au plus).

=== "curl"

    ```bash
    curl -s "$API/file/?page_size=2"
    ```

=== "Python"

    ```python
    page = requests.get(f"{API}/file/", params={"page_size": 2}).json()
    print(page["count"], [f["name"] for f in page["results"]])
    ```

Un fichier porte tout son contexte : sa `recording_session` (avec le `protocol`, le `laboratory`, les
`animal_profiles`, le matériel et les `references`), ses `subjects`, son dépôt et ses `usv_detections` (un résumé
par outil).

### Chercher et filtrer

`search` regarde dans les noms des fichiers, des sessions, des animaux et du matériel, dans le protocole, le
laboratoire et le nom de l'auteur ; plusieurs mots doivent tous être trouvés. Combinez-le avec les filtres :

| Paramètre | Valeur | Exemple |
|---|---|---|
| `search` | des mots | `search=Shank2` |
| `species` | nom scientifique | `species=Mus musculus` |
| `sex` | `male`, `female` | `sex=female` |
| `age` | `pup`, `juvenile`, `adult` | `age=pup` |
| `file_format` | format, séparés par des virgules | `file_format=WAV` |
| `repository` | nom | `repository=Zenodo` |
| `filter` | `is_valid_link` garde les fichiers téléchargeables | `filter=is_valid_link` |
| `recording_session` | id d'une session | `recording_session=12` |

```bash
curl -s -G "$API/file/" \
     --data-urlencode "species=Mus musculus" --data-urlencode "sex=female" \
     --data-urlencode "age=pup" --data-urlencode "file_format=WAV" \
     --data-urlencode "filter=is_valid_link" -d page_size=5
```

Les valeurs qui existent, pour construire un formulaire, sont à `GET /api/file/filters/` :

```json
{"species": ["Mus musculus", "Rattus norvegicus"], "sex": ["female", "male"], "age": ["adult", "pup"],
 "format": ["WAV"], "repository": ["Zenodo"]}
```

!!! note "Seul ce qui est validé est cherché"
    La recherche ne trouve jamais un fichier par quelque chose qu'un administrateur n'a pas validé, et les réponses
    ne le montrent jamais (voir [Droits et statuts](../rights.md#une-session-publique-se-modifie-sans-etre-cachee)).

### Obtenir un fichier

```bash
curl -s "$API/file/55/"
```

Le fichier d'une session en brouillon, ou en attente de validation, répond **404** à tout le monde sauf à son auteur
et aux administrateurs.

### Télécharger, et le compter

Le téléchargement lui-même est un lien : `file["link"]` (ou le DOI, `https://doi.org/<doi>`) pointe vers le dépôt.
Pour garder le compteur honnête, dites à mouseTube quand vous téléchargez :

```bash
curl -s -X POST "$API/file/55/download/"
# {"downloads": 113, "counted": true}
```

C'est ouvert à tous et compté **une fois par visiteur, fichier et heure**, donc un nouvel essai ne le gonfle pas.

### Fichiers d'un enregistrement, et zips

Les fichiers de l'enregistrement Zenodo d'un fichier (l'enregistrement, les tableaux des outils de détection, les
images), pour tout le monde :

```bash
curl -s "$API/file/55/zenodo-files/"
# {"record": "https://zenodo.org/records/20622419",
#  "files": [{"name": "090916_S2-2-22_P06_2min.wav", "size": 72100000,
#             "url": "https://zenodo.org/records/20622419/files/090916_S2-2-22_P06_2min.wav?download=1"}, ...]}
```

La liste est gardée une heure. Elle répond **404** pour un fichier que Zenodo n'héberge pas, **429** quand trop
d'enregistrements ont été lus dans la minute et **502** quand Zenodo ne répond pas.

Le zip d'un jeu de données ou d'un enregistrement est réservé aux **utilisateurs connectés**. Un lien ne peut pas
porter votre connexion : demandez d'abord un jeton (valable **deux minutes, une seule fois**), puis téléchargez avec :

```bash
TOKEN=$(curl -s -X POST "$API/dataset/7/download/" \
  -H "Authorization: Bearer $ACCESS" -H "Content-Type: application/json" \
  -d '{"scope": "sound"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
curl -s -o dataset.zip "$API/dataset/7/download/?token=$TOKEN"
```

`scope` vaut `sound` (les enregistrements du jeu de données) ou `all` (par défaut : tous les fichiers de leurs
enregistrements Zenodo, un dossier par enregistrement). Pour un seul enregistrement, `POST $API/file/<id>/record-download/`.
La réponse du `POST` donne aussi `files`, `bytes` et `left_out` (les fichiers du jeu de données que Zenodo n'héberge
pas, absents du zip). Elle répond **413** quand le zip est trop gros, **429** quand vous avez déjà un téléchargement
en cours ou que le serveur est occupé. Un fichier illisible est listé dans `_errors.txt` dans le zip.

### Résultats des outils de détection

Un fichier liste ses `usv_detections` (outil, nombre d'appels, cadence, fréquences). Les appels eux-mêmes se lisent
à la demande :

```bash
curl -s "$API/usv-detection/237/"      # {"tool": "avisoft", "calls": [ {start, end, …}, … ], …}
curl -s "$API/usv-detection/tools/"    # les six outils, leurs formats de fichier et leur citation
```

### Jeux de données

```bash
curl -s "$API/dataset/"                      # les jeux de données, avec leurs fichiers et sessions
curl -s "$API/dataset/7/"                    # un seul
curl -s "$API/dataset/7/metadata/"           # le JSON de métadonnées : sessions, protocoles, animaux, matériel
curl -s "$API/dataset/metadata/"             # la même chose pour tous les jeux
```

Le JSON de métadonnées est le format des jeux de données de mouseTube 0.5 : `{"dataset": {"name", "description",
"recording_session_list": [ … ]}}`. Les e-mails des contacts ne sont jamais exportés.

### Matériel, protocoles, animaux

| Route | Paramètres utiles |
|---|---|
| `/api/software/` | `search`, `filter=acquisition|analysis|acquisition and analysis`, `used=1` (utilisé par une session publique), `documented=1` |
| `/api/hardware/` | `search`, `type=microphone|soundcard|speaker|amplifier`, `used=1`, `documented=1` |
| `/api/protocol/` | `animals_sex`, `animals_age`, `context_duration`… (chaque champ du protocole) |
| `/api/animalprofile/` | `sex`, `age`, `genotype`, `strain`, `species`, `treatment`, `diet` |
| `/api/strain/`, `/api/species/`, `/api/laboratory/`, `/api/reference/`, `/api/contact/` | `search` |
| `/api/repository/` | `search` |

```bash
curl -s "$API/hardware/?type=microphone&used=1&documented=1"
```

Quand vous êtes connecté, `?status=draft` (ou `waiting validation`) restreint la liste à **vos propres** fiches dans
cet état ; `?favorites=1` et `?mine=1` fonctionnent aussi sur le matériel et les logiciels.

## Écrire les données

Tous les appels ci-dessous demandent l'en-tête `Authorization: Bearer <jeton d'accès>`.

```python
tokens = requests.post(
    f"{HOST}/auth/jwt/create/", json={"username": "alice", "password": "…"}
).json()
H = {"Authorization": f"Bearer {tokens['access']}"}
```

### Décrire un enregistrement, pas à pas

L'ordre est celui du site : ce que la session utilise, puis la session, puis ses fichiers.

**1. Les pièces.** Chacune est créée en `draft`, privée pour vous.

```python
lab = requests.post(
    f"{API}/laboratory/",
    headers=H,
    json={"name": "Neuro-PSI", "country": "FR", "institution": "CNRS"},
).json()
mic = requests.post(
    f"{API}/hardware/",
    headers=H,
    json={"name": "CM16/CMPA", "type": "microphone", "made_by": "Avisoft"},
).json()
prot = requests.post(
    f"{API}/protocol/",
    headers=H,
    json={
        "animals_sex": "male(s)",
        "animals_age": "pup",
        "animals_housing": "grouped",
        "context_number_of_animals": "2",
        "context_duration": "short term (<1h)",
        "context_cage": "unfamiliar test cage",
        "context_bedding": "bedding",
        "context_light_cycle": "day",
    },
).json()  # son nom est construit : "2MPG_S_UCBD"
strain = requests.post(
    f"{API}/strain/",
    headers=H,
    json={"name": "C57BL/6J", "background": "C57BL/6J", "species_id": 1},
).json()
profile = requests.post(
    f"{API}/animalprofile/",
    headers=H,
    json={
        "name": "C57BL/6J male pups",
        "strain_id": strain["id"],
        "sex": "male",
        "age": "pup",
        "genotype": "wt",
    },
).json()
```

- Un **protocole** est **validé d'office** (un code, pas de texte libre) ; poster les mêmes champs à nouveau
  renvoie le même protocole.
- Ajoutez un terme de vocabulaire à un champ avec son CURIE, trouvé avec `GET /api/ontology/search/?field=sex&q=male`
  (connecté) : `"sex_term": {"curie": "PATO:0000384"}`. Le terme est vérifié à sa source. Une souche dont
  `ontology_term` est renseigné est validée d'office, et il y en a une par terme.

**2. La session.**

```python
session = requests.post(
    f"{API}/recording-session/",
    headers=H,
    json={
        "name": "Pup isolation calls",
        "is_multiple": True,
        "protocol_id": prot["id"],
        "laboratory_id": lab["id"],
        "animal_profile_ids": [profile["id"]],
        "equipment_acquisition_hardware_microphone_ids": [mic["id"]],
    },
).json()
```

Les champs `…_ids` prennent les ids de fiches que vous pouvez utiliser (**validées** ou **les vôtres**) :
`protocol_id`, `laboratory_id`, `animal_profile_ids`, `equipment_acquisition_software_ids` (ids de *versions de
logiciel*), `equipment_acquisition_hardware_soundcard_ids`, `…_speaker_ids`, `…_amplifier_ids`,
`…_microphone_ids`, `references_ids`, `study_ids` (les vôtres seulement). Une session unique
(`"is_multiple": false`) demande aussi une `date`. La réponse montre toute la session avec ses objets imbriqués.

**3. Les fichiers.** Deux façons.

=== "Un fichier qui a déjà un DOI et un lien"

    ```python
    requests.post(
        f"{API}/file/",
        headers=H,
        json={
            "name": "pup1.wav",
            "format": "WAV",
            "link": "https://zenodo.org/records/1/files/pup1.wav",
            "doi": "10.5281/zenodo.1",
            "recording_session_id": session["id"],
        },
    )
    ```

    mouseTube l'enregistre et ne dépose rien.

=== "Laisser mouseTube le déposer"

    ```python
    with open("pup1.wav", "rb") as f:
        up = requests.post(f"{API}/file/upload_async/", headers=H, files={"file": f}).json()
    # {"temp_path": "/media/temp/<id>_pup1.wav"}
    file = requests.post(
        f"{API}/file/",
        headers=H,
        json={
            "name": "pup1.wav",
            "link": up["temp_path"],
            "recording_session_id": session["id"],
            "repository_id": 1,
        },
    ).json()
    status = requests.get(
        f"{API}/file/{file['id']}/status/", headers=H
    ).json()  # suivre le traitement
    ```

    Le fichier est lu, son en-tête WAV remplit le format, la fréquence d'échantillonnage et la durée, et il est
    envoyé au dépôt en arrière-plan (`status` : `pending`, `processing`, `done` ou `error`, avec un
    `error_message` lisible). La limite est de 5 Gio par défaut (**413** au-delà).

Vous pouvez ajouter les **résultats d'un outil de détection** à un fichier qui vous appartient :

```python
requests.post(
    f"{API}/file/{file['id']}/usv-detections/",
    headers=H,
    files={"file": open("usvseg.csv", "rb")},
    data={"tool": "usvseg", "tool_version": "1.0", "deposit": "false"},
)
```

### Partager une session

```python
r = requests.patch(
    f"{API}/recording-session/{session['id']}/", headers=H, json={"status": "shared"}
).json()
print(r["status"], r["pending_entries"])
```

- Si tout ce que la session utilise est validé : `status` est **`shared`** et la session est publique.
- Sinon **`waiting validation`**, et `pending_entries` liste ce qu'un administrateur doit valider
  (`[{"kind": "hardware", "name": "CM16/CMPA", "status": "draft"}]`). La session est privée et verrouillée.
- `PATCH` `{"status": "draft"}` **retire** une session en attente, pour que vous puissiez la modifier.

Les droits d'une session sont dans son champ `rights` (`can_edit`, `can_withdraw`, `can_share`, `can_delete`, et la
raison quand elle est verrouillée), si bien qu'un client n'a pas à deviner.

### Demander la relecture d'une fiche

```python
requests.patch(
    f"{API}/hardware/{mic['id']}/", headers=H, json={"status": "waiting validation"}
)
```

Seul un administrateur met `validated` (tout autre reçoit **400**).

### Publier dans un dépôt

Une session **partagée**, qui a un fichier prêt et n'utilise rien qui attende la validation peut être déposée, avec
un DOI.

```python
# 1. la description qui serait envoyée, à montrer ou modifier
payload = requests.get(
    f"{API}/repository/1/sessions/{session['id']}/payload/", headers=H
).json()
# 2. le dépôt, en arrière-plan
job = requests.post(
    f"{API}/file/publish_session/",
    headers=H,
    json={
        "recording_session_id": session["id"],
        "repository_id": 1,
        "payload": payload,
    },
).json()
# {"message": "Publishing started…", "task_id": "…"}
state = requests.get(
    f"{API}/recording-session/get_task_status",
    headers=H,
    params={"task_id": job["task_id"]},
).json()
```

- **409** si la session n'est pas partagée, utilise des fiches en attente de validation, ou (publiée) n'a rien de
  nouveau : ajoutez un fichier pour faire une nouvelle version.
- Une session publiée que vous modifiez garde sa notice à jour (`zenodo_state`) ; les fichiers ajoutés ensuite font
  une **nouvelle version** avec son propre DOI.

**Publier une fois validée.** Pendant qu'une session attend la validation, approuvez l'aperçu pour qu'elle parte
toute seule :

```python
requests.post(
    f"{API}/recording-session/{session['id']}/auto-publish/",
    headers=H,
    json={"repository_id": 1, "payload": payload},
)  # DELETE sur la même URL pour annuler
```

### Favoris

```python
requests.post(
    f"{API}/favorite/",
    headers=H,
    json={"content_type_name": "hardware", "object_id": mic["id"]},
)
requests.get(f"{API}/favorite/", headers=H)  # les vôtres seulement
```

Permis : protocol, hardware, software, animalprofile, strain, laboratory, reference, contact.

## Administrateurs

Ces routes répondent **403** à tous les autres.

| But | Appel |
|---|---|
| Ce qui attend une décision | `GET /api/review/` (compteurs par type), `GET /api/review/<kind>/` (le plus ancien d'abord). Types : `accounts`, `sessions`, `software`, `hardware`, `laboratories`, `references`, `contacts`, `strains`, `animal-profiles` |
| Valider ou renvoyer | `POST /api/review/<kind>/decision/` with `{"action": "validate" \| "send_back", "ids": [1, 2], "reason": "…"}` |
| Vérifier les liens de téléchargement | `GET /api/admin/link-check/` (état), `POST` pour lancer |
| Mettre les images d'un fichier | `POST /api/file/<id>/images/` (`spectrogram`, `plot`), `DELETE …?field=plot` |
| Créer un jeu de données | `POST /api/dataset/` |

Valider une **session** valide tout ce qu'elle utilise ; l'auteur est prévenu par e-mail.
