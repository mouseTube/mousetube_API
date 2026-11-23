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
