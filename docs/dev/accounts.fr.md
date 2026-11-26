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
- Les jetons d'accès et de rafraîchissement déjà émis restent valables après un changement (ils ne sont pas révoqués) ;
  le jeton d'accès dure une heure.

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
