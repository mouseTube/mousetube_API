# Droits et statuts

Cette page dit, pour chaque type d'objet, **qui peut lire, modifier, supprimer et publier, et comment cela dépend
de son statut**. C'est la référence pour le site, pour l'API et pour l'admin Django : tous appliquent les mêmes
règles. Chaque règle ci-dessous est vérifiée par un test (voir [Où vivent les règles](#ou-vivent-les-regles)).

!!! tip "Lire les réponses de l'API"
    - **401** – vous n'êtes pas connecté (les visiteurs ne peuvent pas du tout le faire).
    - **403** – vous pouvez voir l'objet mais pas faire cela.
    - **404** – vous ne pouvez même pas le voir : un objet privé à quelqu'un d'autre répond « introuvable », comme
      s'il n'existait pas.

## Les quatre rôles

| Rôle | Qui | Comment l'API le reconnaît |
|---|---|---|
| **Visiteur** | N'importe qui, sans compte | Pas de jeton |
| **Utilisateur** | Connecté, compte actif | Un jeton valide (le compte a été confirmé par e-mail, puis activé par un administrateur) |
| **Auteur** | L'utilisateur qui a créé l'objet | `created_by` est l'utilisateur |
| **Administrateur** | L'équipe de mouseTube | `is_staff` (donné dans l'admin Django, jamais par l'API) |

Un administrateur peut tout ce que peut un utilisateur, et plus. Il modère par la
[page Review et l'admin Django](moderation.md) ; l'API des catalogues accepte aussi ses modifications.

## Les statuts

=== "Fiches de catalogue"

    Laboratoire, référence, contact, matériel, logiciel, souche, profil d'animaux (et, sans relecture, étude) :

    <span class="pill grey">draft</span> → <span class="pill blue">waiting validation</span> → <span class="pill green">validated</span>

    - l'auteur la crée en **draft** et peut l'envoyer en relecture (**waiting validation**) ou la reprendre ;
    - seul un administrateur la rend **validated** (ou la renvoie en draft avec une raison) ;
    - une fiche **validated** est publique et verrouillée pour son auteur.

=== "Sessions d'enregistrement"

    <span class="pill grey">draft</span> → <span class="pill blue">waiting validation</span> → <span class="pill green">shared</span> → <span class="pill red">published</span>

    - **draft** : travail en cours, privé ;
    - **waiting validation** : l'auteur a demandé de partager une session qui utilise des fiches que personne n'a
      encore validées ; elle reste privée et verrouillée pendant qu'un administrateur la lit ;
    - **shared** : publique ; l'auteur continue à la modifier ;
    - **published** : partagée *et* déposée dans un dépôt (Zenodo) avec un DOI.

=== "Fichiers"

    Un fichier n'a pas de statut de modération propre. Il suit sa session : privé tant que la session est un
    brouillon ou attend la relecture, public une fois qu'elle est partagée. Son `status` (`pending`, `processing`,
    `done`, `error`) n'est que l'état de son traitement et de son dépôt.

## Fiches de catalogue

La même règle s'applique aux sept catalogues modérés. Elle est vérifiée cellule par cellule pour chacun par
`test_rights_matrix.py`.

<table>
<thead>
<tr><th>Statut de la fiche</th><th>Visiteur</th><th>Autre utilisateur</th><th>Auteur</th><th>Administrateur</th></tr>
</thead>
<tbody>
<tr><td><span class="pill grey">draft</span></td>
<td><span class="no">rien (404)</span></td>
<td><span class="no">rien (404)</span></td>
<td><span class="yes">lire, modifier, supprimer</span>, envoyer en relecture</td>
<td><span class="yes">tout</span></td></tr>
<tr><td><span class="pill blue">waiting validation</span></td>
<td><span class="no">rien (404)</span></td>
<td><span class="no">rien (404)</span></td>
<td><span class="yes">lire, modifier</span>, retirer. <span class="no">Pas supprimer (403)</span></td>
<td><span class="yes">tout</span>, valide ou renvoie</td></tr>
<tr><td><span class="pill green">validated</span></td>
<td><span class="yes">lire</span></td>
<td><span class="yes">lire</span>, l'utiliser dans une session</td>
<td><span class="yes">lire</span>. <span class="no">Pas modifier, pas supprimer (403)</span></td>
<td><span class="yes">tout</span></td></tr>
</tbody>
</table>

Plus précisément :

| Action | Règle |
|---|---|
| **Lister** | Tout le monde voit les fiches validées. Un utilisateur connecté voit aussi les siennes. Un administrateur voit tout. Demander un statut (`?status=draft`) ne fait que restreindre ce que vous pouvez déjà voir. |
| **Créer** | Tout utilisateur connecté. La fiche commence en `draft`. Un visiteur reçoit 401. |
| **Modifier** | L'auteur tant que la fiche est `draft` ou `waiting validation` ; un administrateur toujours. Personne d'autre. |
| **Supprimer** | L'auteur tant que c'est un `draft` (pas une fois soumise : retirez-la d'abord) ; un administrateur toujours. |
| **Changer le statut** | L'auteur la fait passer entre `draft` et `waiting validation`. Seul un administrateur met `validated` (tout autre reçoit 400 « Only administrators can validate »). Une fiche **créée par un administrateur** est `validated` tout de suite, sauf si la requête demande un autre statut. |
| **L'utiliser dans une session** | Tout utilisateur peut attacher une fiche `validated` ou une des siennes. L'API refuse le brouillon d'un autre. |

### Ce qui diffère de la règle

| Objet | Différence |
|---|---|
| **Étude** | Privée à son auteur (et aux administrateurs) : personne d'autre ne la liste, ne la choisit ni ne l'ouvre. Elle n'est **jamais relue**, donc elle reste `draft`. Son nom reste montré sur une session partagée. Un visiteur reçoit 401. |
| **Protocole** | Son nom est un code construit à partir de ses champs et il n'a pas de texte libre, donc il est **validé dès qu'il est enregistré**. En créer un qui existe déjà renvoie l'existant. Il est ensuite verrouillé pour son auteur comme toute fiche validée. |
| **Souche d'une ontologie** | Validée d'office : son terme est vérifié à la source (EFO, Rat Strain Ontology). Il n'y a qu'une souche par terme : la redemander renvoie l'existante. |
| **Espèce** | Tout le monde lit. Seul un administrateur crée, modifie ou supprime. |
| **Logiciel** | Un verrou en plus : un logiciel ou une version que **des sessions d'autres personnes utilisent** ne peut être ni modifié ni supprimé, même par un administrateur (le modifier dans l'admin Django si c'est vraiment nécessaire). Supprimer la dernière version d'un logiciel supprime le logiciel. |
| **Contact** | Lisible comme les autres, mais l'**e-mail est caché aux visiteurs** (et ils ne peuvent pas le chercher). |
| **Sujet** (un animal individuel) | N'a pas de statut. Un sujet est listé avec les fichiers visibles : un visiteur ne rencontre que ceux des sessions publiques ; l'auteur les siens ; un administrateur tous. |
| **Favori** | Chaque utilisateur ne voit et ne retire que ses propres favoris. Cibles permises : protocole, matériel, logiciel, profil d'animaux, souche, laboratoire, référence, contact. |
| **Profil d'utilisateur** | Un utilisateur ne voit et ne modifie que **son** profil ; un administrateur voit tous (les profils contiennent des e-mails). |
| **Dépôt** | Tout le monde lit la liste. Il se gère dans l'admin Django. |

## Sessions d'enregistrement

Une session est le centre des données : protocole, animaux, matériel et fichiers en dépendent. Ses règles sont
décidées à un seul endroit, `utils/session_rights.py`, et l'API les envoie avec chaque session (le champ
`rights`), si bien que le site n'a qu'à les suivre.

<table>
<thead>
<tr><th>Statut</th><th>Visiteur / autre utilisateur</th><th>Auteur</th><th>Administrateur</th></tr>
</thead>
<tbody>
<tr><td><span class="pill grey">draft</span></td>
<td><span class="no">rien</span> (la session et ses fichiers sont privés)</td>
<td><span class="yes">modifier</span>, <span class="yes">partager</span>, <span class="yes">supprimer</span>, ajouter des fichiers</td>
<td><span class="yes">tout</span> (admin Django, page Review)</td></tr>
<tr><td><span class="pill blue">waiting validation</span></td>
<td><span class="no">rien</span></td>
<td><span class="no">ne peut pas modifier (403)</span> ; <span class="yes">retirer</span> (retour en draft) ; <span class="no">ne peut pas supprimer</span> ; peut encore ajouter des fichiers</td>
<td><span class="yes">tout</span> : valide la session avec ce qu'elle utilise, ou la renvoie</td></tr>
<tr><td><span class="pill green">shared</span></td>
<td><span class="yes">lire</span> (parties validées seulement)</td>
<td><span class="yes">modifier</span> (elle reste publique), <span class="yes">publier dans un dépôt</span>, ajouter des fichiers ; <span class="no">ne peut ni supprimer, ni annuler le partage</span></td>
<td><span class="yes">tout</span></td></tr>
<tr><td><span class="pill red">published</span></td>
<td><span class="yes">lire</span> (parties validées seulement), DOI</td>
<td><span class="yes">modifier</span> (sa notice dans le dépôt suit), <span class="yes">nouvelle version</span> en ajoutant des fichiers ; <span class="no">ne peut pas supprimer</span></td>
<td><span class="yes">tout</span></td></tr>
</tbody>
</table>

### Le partage

Quand l'auteur demande à partager un brouillon :

- si **tout ce que la session utilise est validé**, elle devient `shared` tout de suite ;
- sinon elle devient `waiting validation` (privée, verrouillée) et un administrateur est prévenu par e-mail. Elle
  devient `shared` quand un administrateur la valide **avec** ce qu'elle utilise, ou dès que la dernière fiche
  manquante est validée une par une. L'auteur est prévenu par e-mail. Un administrateur peut aussi la renvoyer en
  draft avec une raison.
- quand un **administrateur** partage une session (le statut `shared` dans la requête), les fiches qu'elle utilise sont
  validées dans le même geste, comme le fait l'action de l'admin : une session partagée ne garde jamais une fiche en
  brouillon, ce qui bloquerait son dépôt dans un dépôt de données.

L'auteur peut retirer une session qui attend la relecture, puis la modifier. Une session partagée ne peut pas être
remise en brouillon par son auteur.

### Une session publique se modifie sans être cachée

Une **session partagée ou publiée reste modifiable par son auteur et reste publique**. Ce qu'elle utilise et que
personne n'a encore validé (un nouveau microphone, un profil d'animaux, une souche…) est simplement **non montré
aux autres** jusqu'à ce qu'un administrateur le valide. L'auteur et les administrateurs voient tout.

Ce que couvre « non montré », sur chaque route publique : la liste et le détail des fichiers, les jeux de données
et leur export de métadonnées, la recherche (une fiche cachée ne peut pas être trouvée par son nom), les sujets, et
le message sur l'état de la notice dans le dépôt. Caché pour les autres : le protocole ou le laboratoire s'ils ne
sont pas validés, chaque profil d'animaux, matériel ou référence non validé, et les références ou contacts non
validés d'un matériel validé.

Tant que quelque chose est caché, la session **ne peut pas être déposée dans un dépôt** (409) : le public ne doit
jamais lire dans la description d'une notice ce que le site lui cache. Une session publiée garde sa notice, dont la
mise à jour attend la validation (`zenodo_state` = `blocked`) puis s'exécute toute seule.

### Où l'API des sessions vous mène

| Requête | Résultat |
|---|---|
| `GET /api/recording-session/` | Les sessions **de l'auteur** (cette route est l'espace de travail de l'auteur ; les sessions publiques se lisent par les fichiers et les jeux de données). |
| `PATCH` d'une session en relecture | 403 avec la raison, sauf si la requête met seulement `status: "draft"` (retirer). |
| `DELETE` d'une session qui n'est pas un brouillon | 403. |
| `POST /api/file/publish_session/` | L'auteur (ou un administrateur) ; 409 si la session utilise des fiches non validées (la réponse nomme chacune, son état et quoi faire, dans `detail` et `entries`), n'est pas partagée, ou n'a rien de nouveau. |
| `POST /api/recording-session/<id>/auto-publish/` | L'auteur, pendant que la session attend la relecture : approuve l'aperçu pour qu'elle soit publiée une fois validée. |

## Fichiers

| Action | Visiteur | Autre utilisateur | Auteur | Administrateur |
|---|---|---|---|---|
| **Voir** le fichier (liste, détail, compteur de téléchargements) | <span class="yes">si sa session est partagée ou publiée</span> | pareil | <span class="yes">toujours</span> | <span class="yes">toujours</span> |
| **Ajouter** un fichier | <span class="no">401</span> | <span class="no">403</span> (pas sa session) | <span class="yes">à sa propre session</span> | <span class="yes">oui</span> |
| **Modifier** le fichier | <span class="no">401</span> | <span class="no">403 / 404</span> | <span class="yes">oui</span> | <span class="yes">oui</span> |
| **Supprimer** le fichier | <span class="no">401</span> | <span class="no">403 / 404</span> | <span class="yes">oui</span>, sauf un fichier d'une version publiée (409) | pareil |
| **Spectrogramme et courbe** | non | non | <span class="no">non (403)</span> | <span class="yes">oui</span> |
| **Ajouter des résultats de détection** (USV) | non | non | <span class="yes">oui</span>, sur son fichier | <span class="yes">oui</span> |
| **Compter un téléchargement** | <span class="yes">oui</span>, une fois par visiteur, fichier et heure | pareil | pareil | pareil |
| **Voir les fichiers de l'enregistrement Zenodo** (`GET /api/file/<id>/zenodo-files/`) | <span class="yes">si sa session est partagée ou publiée</span> | pareil | <span class="yes">toujours</span> | <span class="yes">toujours</span> |
| **Zip d'un enregistrement** (`POST /api/file/<id>/record-download/`) | <span class="no">401</span> | <span class="yes">des fichiers qu'ils peuvent voir</span> | <span class="yes">oui</span> | <span class="yes">oui</span> |
| **Zip d'un jeu de données** (`POST /api/dataset/<id>/download/`) | <span class="no">401</span> | <span class="yes">ce que la page leur montre</span> | pareil | <span class="yes">oui</span>, les brouillons aussi |

Le fichier d'un brouillon ou d'une session en relecture répond **404** à tout le monde sauf à son auteur et aux
administrateurs.

## Surfaces réservées aux administrateurs

| Surface | Ce qu'elle fait |
|---|---|
| **Admin Django** (`/admin/`) | Modération de chaque type, comptes, dépôts. Enregistrer une session comme *shared* valide ce qu'elle utilise. |
| **`/api/review/…`** | La page Review du site : liste ce qui attend, valide ou renvoie, demandes de compte. 403 pour tous les autres. |
| **`/api/admin/link-check/`** | Vérification des liens de téléchargement. |
| **Jeux de données** | Créer, modifier et supprimer sont réservés aux administrateurs ; la lecture est ouverte (une session en brouillon placée dans un jeu reste privée). |
| **Espèces** | Créer, modifier, supprimer. |
| **Spectrogramme et courbe d'un fichier** | Les mettre ou les retirer. |

## Comptes

Un visiteur s'inscrit avec une adresse e-mail institutionnelle. Le compte est **inactif** tant que l'utilisateur
n'a pas confirmé l'e-mail **et** qu'un administrateur ne l'a pas activé ; un compte inactif n'obtient pas de jeton.
ORCID est lié par une preuve signée, jamais saisi. Voir [Demandes de compte](accounts.md).

## Où vivent les règles { #ou-vivent-les-regles }

| Règle | Code | Test |
|---|---|---|
| Qui voit, modifie et supprime une fiche de catalogue | `views.py` (`visible_to`, `IsCreatorOrReadOnly`, le `ModerationMixin` des serializers) | `test_rights_matrix.py` |
| Ce qu'un utilisateur peut faire d'une session | `utils/session_rights.py` (`session_rights`), appliqué par le serializer et `IsCreatorOrReadOnly` | `test_session_rights.py` (chaque statut et chaque rôle) |
| Ce que le public voit d'une session publique | `utils/moderation.py` (`public_session_data`, `sees_everything`), `views.py` (`visible_files`) | `test_public_visibility.py` (lit chaque route publique avec des témoins) |
| Changements de statut et relecture | `utils/moderation.py` (`validate_session`, `promote_ready_sessions`, `send_back`) | `test_security.py` (`ModerationTests`) |
| Publication dans un dépôt | `utils/publication.py`, `tasks.py` | `test_security.py` (`PublishSessionTests`, `AutoPublishTests`) |

!!! note "Quand vous ajoutez un objet ou une route"
    Décidez d'abord sa ligne dans ces tableaux. Un nouveau catalogue modéré rejoint `CatalogRightsTests` ; une
    nouvelle route publique qui montre une session ou ses fiches doit être ajoutée aux routes que
    `test_public_visibility.py` lit.
