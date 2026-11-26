# Demandes de compte

1. L'utilisateur s'inscrit avec une adresse e-mail **institutionnelle** (les fournisseurs personnels comme Gmail sont refusés).
2. Le compte est créé **inactif** et l'utilisateur reçoit un lien pour confirmer l'adresse.
3. Une fois le lien ouvert, `DEFAULT_ADMIN_EMAIL` reçoit un message avec un lien vers le compte dans l'admin. Ouvrir le lien deux fois n'envoie pas un deuxième message.
4. Dans l'admin, **Users**, le filtre *Account request* donne deux listes : *To review (e-mail confirmed)* et *Waiting for e-mail confirmation*. Le lien de l'e-mail à l'administrateur ouvre la première. Pour chaque demande l'administrateur peut :
   - cocher **Active** sur le compte et enregistrer, ou en sélectionner plusieurs et lancer **Activate selected accounts** (refusé si l'e-mail n'est pas confirmé) ;
   - les sélectionner et lancer **Reject selected requests** : une page demande une raison facultative, puis la demande est supprimée et la personne est prévenue par e-mail. Seuls les comptes inactifs qui ne se sont jamais connectés peuvent être rejetés ; si l'e-mail ne peut pas être envoyé, la demande est conservée.
5. L'utilisateur reçoit un e-mail disant que le compte est actif (ou le refus, avec la raison).

## S'inscrire avec ORCID

Le formulaire peut être lancé depuis ORCID. ORCID ne donne que ce qui est public sur la fiche de la personne : le prénom et le nom remplissent le formulaire, et une adresse institutionnelle aussi si elle est publique (une adresse personnelle n'est pas proposée, elle serait refusée). Un nom ou une adresse privés sont laissés à saisir, et le formulaire le dit. L'adresse est confirmée par le lien qui lui est envoyé, comme toute autre : elle n'est jamais tenue pour vérifiée parce qu'ORCID l'a donnée.

## Changer un mot de passe

- **Connecté :** `POST /auth/users/set_password/` avec `current_password`, `new_password` et `re_new_password` (page
  *Mon compte*, onglet *Preferences*, section *Password*). Le mot de passe actuel est demandé, donc une session volée ne
  suffit pas, et aucun mail n'est nécessaire. Le nouveau mot de passe passe par les mêmes validateurs que
  l'inscription. Les essais sont limités comme la connexion (10 par minute et par adresse), parce que le mot de passe
  actuel pourrait y être deviné. L'API ne compare pas `re_new_password` à `new_password` : le formulaire du site le fait.
- **Oublié :** `POST /auth/users/reset_password/` envoie un lien par mail (limité aussi), qui ouvre
  `password/reset/confirm/<uid>/<token>` sur le site.
- Un nouveau mot de passe met fin aux connexions faites avec l'ancien (voir plus bas) : la page reconnecte l'utilisateur.

## Changer l'adresse e-mail

L'adresse sert à retrouver un mot de passe oublié : la changer est aussi sensible que le mot de passe. `email` est en
lecture seule sur `/auth/users/me/` ; le changement passe par deux appels (`utils/email_change.py`), tous deux pour un
utilisateur connecté et limités comme la connexion (10 par minute et par adresse) :

1. `POST /auth/users/change_email/` avec `new_email` et `current_password` (mauvais mot de passe : **400**). La nouvelle
   adresse suit les règles de l'inscription (institutionnelle, différente de l'actuelle). Réponse **202** et un lien
   est envoyé à la **nouvelle** adresse ; l'ancienne reçoit un avis où la nouvelle est en partie masquée. La réponse est
   la même quand l'adresse appartient à un autre compte (la casse ne compte pas) ou quand une limite est atteinte
   (5 demandes par heure et par utilisateur, un mail par adresse toutes les 10 minutes) : rien n'est envoyé et la
   réponse ne le dit pas. Si le mail ne peut pas partir : **503**.
2. `POST /auth/users/confirm_email_change/` avec le `token` du lien (page `/account/confirm-email?token=…` du site ;
   un visiteur non connecté est envoyé à la connexion, puis ramené). Il change `User.email` et remplace l'`EmailAddress`
   de l'utilisateur par la nouvelle, vérifiée. L'ancienne adresse est prévenue.

Le jeton est signé (`django.core.signing`, 24 heures) et contient l'utilisateur, l'ancienne et la nouvelle adresse et une
empreinte du hash du mot de passe. Il ne marche donc qu'**une fois** (l'adresse change, l'ancienne ne correspond plus),
meurt quand le **mot de passe change**, et la confirmation revérifie que l'adresse est libre (dans une transaction, la
ligne de l'utilisateur verrouillée). Il doit être utilisé **connecté en tant que l'utilisateur pour lequel il a été
fait** : sinon le propriétaire d'une adresse saisie par erreur pourrait prendre le compte, puis changer son mot de passe.
Le lien est construit avec `FRONT_URL`, jamais avec l'en-tête `Host`.

## Se déconnecter de partout

`POST /auth/logout_all/` (connecté) met fin à **toutes** les connexions de l'utilisateur faites jusqu'à maintenant, celle
qui le demande comprise ; les autres utilisateurs ne sont pas touchés. Un JWT ne peut pas être repris une fois émis : le
serveur retient donc, par utilisateur, l'instant jusqu'auquel les connexions sont révoquées
(`UserProfile.sessions_revoked_at`) et refuse un jeton d'accès ou de rafraîchissement fait pour une connexion jusqu'à
cet instant (**401**, `session_revoked` ; le renouvellement sur `/auth/jwt/refresh/` aussi). Un jeton porte l'instant de
sa connexion en millisecondes (`iat_ms`) : le `iat` standard est en secondes, trop grossier pour se reconnecter juste
après la révocation. Un jeton fait avant cette fonction n'a pas de `iat_ms` et est lu avec son `iat`.

- C'est aussi fait quand un **mot de passe change**, quel que soit celui qui le change (l'utilisateur, le mail d'un mot de
  passe oublié, un administrateur) : chaque `save()` d'un utilisateur avec un nouveau mot de passe. Un `update()` en bloc
  n'y passe pas.
- Une connexion ne met à jour que la dernière connexion : elle ne met pas fin aux autres connexions de l'utilisateur, donc
  un téléphone et un ordinateur vivent ensemble jusqu'à ce que l'un des deux le demande.
- Rien n'est écrit pour un utilisateur qui n'a jamais révoqué : le champ est vide et la vérification coûte une requête par
  appel.

## Supprimer un compte

Un utilisateur le demande par mail à `mousetube@igbmc.fr` (la section *Delete my account* de la page *Mon compte* l'écrit).
Le droit à l'effacement du RGPD demande une réponse **dans un mois**.

1. **Vérifier qui écrit :** le mail doit venir de l'adresse du compte. Sinon, demandez une confirmation depuis celle-ci.
2. **Supprimer le compte** dans l'administration, *Users* : cochez-le, puis *Delete selected users*. Ne supprimez pas le
   dernier administrateur.
3. **Ce qui reste :** le profil est supprimé avec le compte. Les sessions, fichiers et entrées que l'utilisateur a créés
   sont gardés, avec `created_by` vidé : ils restent, sans lien avec la personne. Les noms saisis en texte (un contact,
   un auteur dans une description) ne sont pas liés au compte et restent ; retirez-les à la main si la personne le demande.
4. **Ce qui n'est pas à nous :** un enregistrement déjà publié sur Zenodo y reste public, selon ses propres règles.
5. **Répondre** à la personne, et garder une trace de la demande et de sa date (pour montrer que le délai a été tenu).
