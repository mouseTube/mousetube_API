# API recipes

What to call to reach a goal, with examples. They use `curl` and Python (`requests`). Every example was run
against a real instance.

```bash
API=http://localhost:8000/api          # your instance, with /api
HOST=http://localhost:8000             # the same, without /api (for /auth/)
```

```python
import requests

API, HOST = "http://localhost:8000/api", "http://localhost:8000"
```

!!! note "Read without a token, write with one"
    The first part needs **no account**. The second part needs a token: see [Authentication](index.md#authentication).

## Read the data

### List the recordings

Every file of a public session. Paginate with `page` and `page_size` (at most 100).

=== "curl"

    ```bash
    curl -s "$API/file/?page_size=2"
    ```

=== "Python"

    ```python
    page = requests.get(f"{API}/file/", params={"page_size": 2}).json()
    print(page["count"], [f["name"] for f in page["results"]])
    ```

A file carries its whole context: its `recording_session` (with the `protocol`, `laboratory`,
`animal_profiles`, the equipment and the `references`), its `subjects`, its repository and its
`usv_detections` (a summary of each tool).

### Search and filter

`search` looks in the names of the files, the sessions, the animals and the equipment, in the protocol, the
laboratory and the author's name; several words must all be found. Combine it with the filters:

| Parameter | Value | Example |
|---|---|---|
| `search` | words | `search=Shank2` |
| `species` | scientific name | `species=Mus musculus` |
| `sex` | `male`, `female` | `sex=female` |
| `age` | `pup`, `juvenile`, `adult` | `age=pup` |
| `file_format` | format, comma separated | `file_format=WAV` |
| `repository` | name | `repository=Zenodo` |
| `filter` | `is_valid_link` keeps the files that can be downloaded | `filter=is_valid_link` |
| `recording_session` | id of a session | `recording_session=12` |

```bash
curl -s -G "$API/file/" \
     --data-urlencode "species=Mus musculus" --data-urlencode "sex=female" \
     --data-urlencode "age=pup" --data-urlencode "file_format=WAV" \
     --data-urlencode "filter=is_valid_link" -d page_size=5
```

The values that exist, to build a form, are at `GET /api/file/filters/`:

```json
{"species": ["Mus musculus", "Rattus norvegicus"], "sex": ["female", "male"], "age": ["adult", "pup"],
 "format": ["WAV"], "repository": ["Zenodo"]}
```

!!! note "Only validated things are searched"
    The search never finds a file by something an administrator has not validated, and the answers never show
    it (see [Rights and statuses](../rights.md#a-public-session-is-edited-without-being-hidden)).

### Get one file

```bash
curl -s "$API/file/55/"
```

A file of a draft session, or of a session that waits for validation, answers **404** to everybody but its
author and the administrators.

### Download, and count it

The download itself is a link: `file["link"]` (or the DOI, `https://doi.org/<doi>`) points to the repository.
To keep the download counter honest, tell mouseTube when you download:

```bash
curl -s -X POST "$API/file/55/download/"
# {"downloads": 113, "counted": true}
```

It is open to everybody and counts **once per visitor, file and hour**, so a retry does not inflate it.

### Files of a record, and zips

The files of the Zenodo record of a file (the recording, the tables of the detection tools, the images), for
everybody:

```bash
curl -s "$API/file/55/zenodo-files/"
# {"record": "https://zenodo.org/records/20622419",
#  "files": [{"name": "090916_S2-2-22_P06_2min.wav", "size": 72100000,
#             "url": "https://zenodo.org/records/20622419/files/090916_S2-2-22_P06_2min.wav?download=1"}, ...]}
```

The list is kept an hour. It answers **404** for a file that Zenodo does not hold, **429** when too many records
were read in the minute and **502** when Zenodo does not answer.

The zip of a dataset or of a record is for **signed-in users** only. A link cannot carry your login, so ask for a
token first (valid **two minutes, once**), then download with it:

```bash
TOKEN=$(curl -s -X POST "$API/dataset/7/download/" \
  -H "Authorization: Bearer $ACCESS" -H "Content-Type: application/json" \
  -d '{"scope": "sound"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
curl -s -o dataset.zip "$API/dataset/7/download/?token=$TOKEN"
```

`scope` is `sound` (the recordings of the dataset) or `all` (the default: every file of their Zenodo records, one
folder per record). For one record, `POST $API/file/<id>/record-download/`. The answer of the `POST` also gives
`files`, `bytes` and `left_out` (the files of the dataset that Zenodo does not hold, not in the zip). It answers
**413** when the zip is too big, **429** when you already have a download running or the server is busy. A file
that could not be read is listed in `_errors.txt` inside the zip.

### Results of the detection tools

A file lists its `usv_detections` (tool, number of calls, rate, frequencies). The calls themselves are read on
demand:

```bash
curl -s "$API/usv-detection/237/"      # {"tool": "avisoft", "calls": [ {start, end, …}, … ], …}
curl -s "$API/usv-detection/tools/"    # the six tools, their file formats and their citation
```

### Datasets

```bash
curl -s "$API/dataset/"                      # the datasets, with their files and sessions
curl -s "$API/dataset/7/"                    # one
curl -s "$API/dataset/7/metadata/"           # the metadata JSON: sessions, protocols, animals, equipment
curl -s "$API/dataset/metadata/"             # the same for all the datasets
```

The metadata JSON is the format of the mouseTube 0.5 datasets: `{"dataset": {"name", "description",
"recording_session_list": [ … ]}}`. E-mails of contacts are never exported.

### Equipment, protocols, animals

| Route | Useful parameters |
|---|---|
| `/api/software/` | `search`, `filter=acquisition|analysis|acquisition and analysis`, `used=1` (used by a public session), `documented=1` |
| `/api/hardware/` | `search`, `type=microphone|soundcard|speaker|amplifier`, `used=1`, `documented=1` |
| `/api/protocol/` | `animals_sex`, `animals_age`, `context_duration`… (every field of the protocol) |
| `/api/animalprofile/` | `sex`, `age`, `genotype`, `strain`, `species`, `treatment`, `diet` |
| `/api/strain/`, `/api/species/`, `/api/laboratory/`, `/api/reference/`, `/api/contact/` | `search` |
| `/api/repository/` | `search` |

```bash
curl -s "$API/hardware/?type=microphone&used=1&documented=1"
```

When you are signed in, `?status=draft` (or `waiting validation`) narrows the list to **your own** entries in
that status; `?favorites=1` and `?mine=1` also work on hardware and software.

## Write the data

All the calls below need the header `Authorization: Bearer <access token>`.

```python
tokens = requests.post(
    f"{HOST}/auth/jwt/create/", json={"username": "alice", "password": "…"}
).json()
H = {"Authorization": f"Bearer {tokens['access']}"}
```

### Describe a recording, step by step

The order is the order of the website: the things the session uses, then the session, then its files.

**1. The pieces.** Each is created as a `draft`, private to you.

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
).json()  # its name is built: "2MPG_S_UCBD"
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

- A **protocol** is **validated at once** (a code, no free text); posting the same fields again returns the
  same protocol.
- Add a vocabulary term to a field with its CURIE, found with `GET /api/ontology/search/?field=sex&q=male`
  (signed in): `"sex_term": {"curie": "PATO:0000384"}`. The term is checked at its source. A strain whose
  `ontology_term` is set is validated at once, and there is one per term.

**2. The session.**

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

The `…_ids` fields take the ids of entries you may use (**validated** or **yours**): `protocol_id`,
`laboratory_id`, `animal_profile_ids`, `equipment_acquisition_software_ids` (ids of *software versions*),
`equipment_acquisition_hardware_soundcard_ids`, `…_speaker_ids`, `…_amplifier_ids`, `…_microphone_ids`,
`references_ids`, `study_ids` (yours only). A single session (`"is_multiple": false`) also needs a `date`.
The answer shows the whole session with its nested objects.

**3. The files.** Two ways.

=== "A file that already has a DOI and a link"

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

    mouseTube records it and deposits nothing.

=== "Let mouseTube deposit it"

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
    ).json()  # follow the processing
    ```

    The file is read, its WAV header fills the format, sampling rate and duration, and it is sent to the
    repository in the background (`status`: `pending`, `processing`, `done` or `error`, with a readable
    `error_message`). The limit is 5 GiB by default (**413** above).

You can add the **results of a detection tool** to a file you own:

```python
requests.post(
    f"{API}/file/{file['id']}/usv-detections/",
    headers=H,
    files={"file": open("usvseg.csv", "rb")},
    data={"tool": "usvseg", "tool_version": "1.0", "deposit": "false"},
)
```

### Share a session

```python
r = requests.patch(
    f"{API}/recording-session/{session['id']}/", headers=H, json={"status": "shared"}
).json()
print(r["status"], r["pending_entries"])
```

- If everything the session uses is validated: `status` is **`shared`** and the session is public.
- Otherwise **`waiting validation`**, and `pending_entries` lists what an administrator has to validate
  (`[{"kind": "hardware", "name": "CM16/CMPA", "status": "draft"}]`). The session is private and locked.
- `PATCH` `{"status": "draft"}` **withdraws** a session that waits, so you can edit it.

The rights of a session are in its `rights` field (`can_edit`, `can_withdraw`, `can_share`, `can_delete`, and the
reason when it is locked), so a client does not have to guess.

### Ask for the review of an entry

```python
requests.patch(
    f"{API}/hardware/{mic['id']}/", headers=H, json={"status": "waiting validation"}
)
```

Only an administrator sets `validated` (anyone else gets **400**).

### Publish in a repository

A session that is **shared**, has a file ready and uses nothing waiting for validation can be deposited, with a
DOI.

```python
# 1. the description that would be sent, to show or edit
payload = requests.get(
    f"{API}/repository/1/sessions/{session['id']}/payload/", headers=H
).json()
# 2. the deposit, in the background
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

- **409** if the session is not shared, uses entries that wait for validation, or (published) has nothing new:
  add a file to make a new version.
- A published session you edit keeps its record up to date (`zenodo_state`); files added later make a **new
  version** with its own DOI.

**Publish once validated.** While a session waits for validation, approve the preview so that it goes out by
itself:

```python
requests.post(
    f"{API}/recording-session/{session['id']}/auto-publish/",
    headers=H,
    json={"repository_id": 1, "payload": payload},
)  # DELETE the same URL to cancel
```

### Favorites

```python
requests.post(
    f"{API}/favorite/",
    headers=H,
    json={"content_type_name": "hardware", "object_id": mic["id"]},
)
requests.get(f"{API}/favorite/", headers=H)  # yours only
```

Allowed: protocol, hardware, software, animalprofile, strain, laboratory, reference, contact.

## Administrators

These routes answer **403** to everybody else.

| Goal | Call |
|---|---|
| What waits for a decision | `GET /api/review/` (counts per kind), `GET /api/review/<kind>/` (oldest first). Kinds: `accounts`, `sessions`, `software`, `hardware`, `laboratories`, `references`, `contacts`, `strains`, `animal-profiles` |
| Validate or send back | `POST /api/review/<kind>/decision/` with `{"action": "validate" \| "send_back", "ids": [1, 2], "reason": "…"}` |
| Check the download links | `GET /api/admin/link-check/` (state), `POST` to start |
| Set the images of a file | `POST /api/file/<id>/images/` (`spectrogram`, `plot`), `DELETE …?field=plot` |
| Create a dataset | `POST /api/dataset/` |

Validating a **session** validates everything it uses; the author is told by e-mail.
