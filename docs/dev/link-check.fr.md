# Vérification des liens de téléchargement

Les fichiers de mouseTube sont pour la plupart hébergés ailleurs (Zenodo, d'autres serveurs) : un lien peut cesser
de répondre. `File.is_valid_link` dit s'il l'a fait la dernière fois qu'on l'a regardé.

## Depuis le site (administrateurs)

Le profil d'un administrateur a un bouton **Check links** à côté de *Review* ; il ouvre `/check-links`. La page lance
la vérification en arrière-plan, montre une barre de progression avec le temps restant et les comptes (répondent,
ne répondent pas, non vérifiés, occupés), et liste les liens qui ne répondent pas. On peut la quitter et la rouvrir :
elle retrouve la vérification là où elle en est. La page, comme les routes qu'elle utilise, est réservée aux
administrateurs.

- `POST /api/admin/link-check/` lance la vérification (tâche `check_dead_links`, Celery) ; `409` pendant qu'une
  tourne (une à la fois).
- `GET /api/admin/link-check/` donne son état, le nombre de liens valides et les 200 premiers qui ne répondent pas.
  L'état est gardé dans le cache (partagé par l'API et le worker) une semaine ; le verrou d'une vérification morte est
  libéré au bout de 6 heures au plus.

## Comment un lien est regardé

Une requête par seconde (les serveurs, Zenodo en premier, ne doivent pas être submergés), `HEAD` d'abord, puis `GET`
si le serveur le refuse. Chaque fichier finit dans l'un de quatre états :

- **répond** (statut inférieur à 400) : le fichier redevient valide s'il ne l'était pas ;
- **ne répond pas** (erreur ou statut 400 et plus) : le fichier est marqué non valide ;
- **non vérifié** : un lien qui n'est pas `http(s)` ou qui mène à une adresse non publique, redirections comprises
  (localhost, réseau privé, lien local) : les liens sont écrits par des utilisateurs, le serveur ne doit pas être
  amené à regarder son propre réseau ;
- **occupé** (429) : le serveur a demandé de ralentir, rien n'est conclu.

La pause n'est prise qu'après un lien réellement regardé : une vérification prend au moins une seconde environ par
tel lien (plus d'une demi-heure pour 1600 liens).

## En ligne de commande

`python manage.py check_dead_links` fait la même chose, avec le même code, et `--fill_name` prend aussi le nom du
fichier dans la réponse quand il n'en a pas.
