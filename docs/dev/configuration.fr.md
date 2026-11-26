# Configuration

Les réglages lisent `.env` à la racine du projet, puis `/etc/mousetube/mousetube.env` s'il n'y a pas de `.env`.
Copiez l'exemple et remplissez-le (`cp .env.example .env`) : voir aussi le [README](https://github.com/mouseTube/mousetube_API#2-create-a-env-file).

## Variables d'environnement

| Variable | Obligatoire | Défaut | Notes |
|---|---|---|---|
| `DEBUG` | non | `false` | `true` seulement pour le développement local. |
| `SECRET_KEY` | **oui quand `DEBUG` est faux** | aucun | L'application refuse de démarrer sans elle. Générez-en une avec `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`. |
| `ALLOWED_HOSTS` | oui en production | `localhost,127.0.0.1` | Séparés par des virgules. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | oui en production | localhost:3000 et mousetube.local | Origines du site, séparées par des virgules. |
| `FRONT_DOMAIN` | oui en production | `localhost:3000` | Utilisé dans les liens des e-mails et la redirection ORCID. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | oui | hôte `127.0.0.1`, port `3306` | `DB_ROOT_PASS` est aussi lu par l'entrypoint Docker. |
| `DB_SSL`, `DB_SSL_CA`, `DB_SSL_CERT`, `DB_SSL_KEY` | non | `False` | |
| `CELERY_BROKER_URL` | oui | `redis://127.0.0.1:6379/0` | Redis, voir l'étape 4. |
| `CACHE_URL` | non | même serveur Redis, base `1` | Cache partagé utilisé par les limites de débit. |
| `DRF_NUM_PROXIES` | **oui derrière des proxys** | `0` | Nombre de proxys inverses devant Django (HAProxy + nginx = `2`). Avec `0`, chaque visiteur partage l'IP du proxy, donc la limite de connexion (10/min) s'applique à tout le site (le conteneur avertit au démarrage quand c'est `0` hors debug). Vérifiez que votre proxy renseigne `X-Forwarded-For`. |
| `SECURE_HSTS_SECONDS` | non | `31536000` | Appliqué seulement quand `DEBUG` est faux. |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `FRONT_SCHEME` | non | `true` (redirection : `true` sauf `DEBUG`), `true`, `true`, `https` sauf `DEBUG` | Seulement pour un site servi en **http** sur un réseau interne, où aucun proxy n'ajoute le https : mettre les trois premières à `false` et `FRONT_SCHEME=http`. Sans cela, l'API redirige toute requête vers https, le navigateur refuse les cookies de session et CSRF (l'administration et la connexion ORCID ne marchent donc pas) et les liens des e-mails commencent par `https`. Les cookies sont alors `SameSite=Lax`, ce qui suffit quand le site et l'API sont derrière la même adresse. Jamais en production. |
| `USE_X_FORWARDED_HOST` | non | `false` | |
| `ZENODO_API`, `ZENODO_TOKEN` | pour publier | URL du bac à sable, vide | Le jeton est envoyé dans un en-tête Bearer, jamais dans une URL. |
| `CLIENT_ID`, `CLIENT_SECRET` | pour la connexion ORCID | vide | Application OAuth ORCID. |
| `REQUIRE_INSTITUTIONAL_EMAIL` | non | `true` | L'inscription est refusée pour les adresses personnelles (Gmail, Outlook...), voir `mousetube_api/utils/email_domains.py`. Mettez `false` en développement local si vous n'avez qu'une adresse personnelle. |
| `MAX_UPLOAD_SIZE` | non | `5368709120` (5 Gio) | Plafond d'un fichier envoyé, en octets. Gardez `client_max_body_size` de nginx au moins aussi grand. |
| `UPLOAD_FREE_SPACE_RESERVE` | non | `1073741824` (1 Gio) | Espace disque libre qu'un envoi laisse toujours. Ce qu'un fichier peut peser à un moment donné est le plus petit de `MAX_UPLOAD_SIZE` et de ce que le disque contient (divisé par deux quand la copie temporaire et `media/` partagent un disque, moins les envois en cours et cette réserve) : `GET /api/file/upload-limit/` le donne, et le formulaire de fichier le vérifie avant d'envoyer. |
| `DATASET_ZIP_MAX_FILES`, `DATASET_ZIP_MAX_BYTES`, `DATASET_ZIP_PARALLEL` | non | `500`, `21474836480` (20 Gio), `2` | Le zip d'un dataset (utilisateurs connectés seulement) contient les fichiers hébergés par Zenodo. Il est envoyé pendant qu'on le fabrique : rien n'est écrit sur le serveur, donc pas d'espace disque à compter ni de reste à nettoyer. Ces réglages limitent les fichiers et les octets d'un zip (vérifiés avant de commencer) et le nombre de zips fabriqués en même temps par tout le serveur (un par utilisateur). |
| `ORCID_BASE_DOMAIN` | non | `orcid.org` | Utilisez `sandbox.orcid.org` avec une application du bac à sable. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_USE_TLS` | **oui en production** | pas de `EMAIL_HOST` = les e-mails s'impriment dans les logs | Serveur SMTP. Nécessaire pour les e-mails de confirmation ci-dessous. |
| `DEFAULT_ADMIN_EMAIL`, `DEFAULT_FROM_EMAIL` | oui en production | `mousetube@igbmc.fr`, `no-reply@mousetube.com` | L'adresse de l'administrateur reçoit les demandes de compte. |
| `ADMIN_BASE_URL` | non | `http://localhost:8000` en debug, sinon `https://FRONT_DOMAIN` | Base du lien vers l'admin écrit dans l'e-mail à l'administrateur. |
| `DJOSER_SEND_ACTIVATION_EMAIL` | non | `true` | Gardez-le activé : il envoie le lien de confirmation aux nouveaux utilisateurs. |

## Variables propres à Docker

`RESET_DB=true` recrée la base. Il est refusé sauf si `DEBUG=true` (un `DEBUG` non défini compte comme faux). Les migrations sont versionnées (`mousetube_api/migrations/`) et appliquées au démarrage du conteneur (`migrate`) ; les conversions de lignes existantes qu'un changement de structure demande sont faites par `python manage.py normalize_data`, que le conteneur lance après `migrate` (sans risque à relancer).
