# Modération : statuts et relecture

Tout ce que les utilisateurs ajoutent aux catalogues (logiciel, matériel, laboratoire, référence, contact,
souche, profil d'animaux) passe par les mêmes états :

`draft` -> `waiting validation` -> `validated`

- Le propriétaire soumet (ou retire) une fiche depuis le site (le bouton **Submit for review** de `ReviewStatus`,
  dans le formulaire de la fiche, dans les listes de matériel et de logiciels et dans le profil pour le
  laboratoire) ; seul un administrateur la valide. Une fiche
  validée ne peut plus être modifiée par son propriétaire.
- Seules les fiches validées sont visibles de tous ; les brouillons et les fiches en attente de relecture ne sont
  visibles que de leur propriétaire.
- **Les études ne sont pas relues.** Une étude est privée à la personne qui l'a faite : chaque utilisateur liste,
  choisit et modifie seulement ses propres études (les administrateurs voient tout), et une session ne peut
  recevoir que des études de son auteur. Rien n'attend de validation, et une session est partagée sans elle. Le
  nom des études d'une session partagée reste montré avec elle, comme le reste de ce que la session dit d'elle-même.
- Une souche choisie dans l'ontologie est validée à sa création (voir [vocabulaires](ontologies.md)).
- Les protocoles n'ont pas de texte libre (un protocole *est* ses attributs), donc ils sont validés
  automatiquement.
- Une session d'enregistrement passe de `draft` à `shared` puis `published` (déposée dans un dépôt, ce qui demande
  une session partagée). Partager une session qui utilise des fiches que personne n'a encore validées la met en
  `waiting validation` : elle est privée et verrouillée jusqu'à ce qu'un administrateur la valide **avec ce qu'elle
  utilise** (action « Validate the sessions and everything they use »), ou jusqu'à ce que les fiches soient
  validées une par une. Une session partagée ou publiée reste modifiable par son auteur et reste publique. Ce
  qu'elle utilise et que personne n'a encore validé (un nouveau microphone, un profil d'animaux...) est **non montré
  aux autres** (listes de fichiers, jeux de données, exports, recherche) jusqu'à ce qu'un administrateur le valide ;
  l'auteur et les administrateurs voient tout. Une session ne peut pas être déposée dans un dépôt tant qu'elle
  utilise de telles fiches : le 409 de `POST /api/file/publish_session/` nomme chaque fiche, son état et quoi faire
  (`detail` et `entries`). Tout type de fiche dont une session a besoin validée peut être soumis depuis le site par son
  propriétaire (un protocole se valide tout seul), donc une session n'est jamais coincée : la sortie est de soumettre la
  fiche, ou pour un administrateur de la valider (ce qu'un administrateur crée, et ce qu'il partage, est validé tout de
  suite). Voir `UnvalidatedIsNotPublicTests`, qui lit chaque route publique.

## Interface de l'administrateur (admin Django)

- L'accueil de `/admin/` liste ce qui attend une décision, avec les demandes de compte.
- Chaque type a un filtre de statut et les actions *Validate the selected entries* et *Send back to draft (with a
  reason)*. Le propriétaire est prévenu par e-mail (quand on a une adresse), et l'administrateur est prévenu
  quand quelque chose est soumis.
- Renvoyer des fiches que des sessions **partagées ou publiées utilisent** prévient l'administrateur, avec le nom des
  sessions : elles restent publiques mais ne peuvent pas être déposées dans un dépôt de données tant que les fiches ne
  sont pas revalidées (la page de relecture montre le même avertissement, `warning` dans la réponse de la décision).
- Une session montre les fiches dont elle a encore besoin qu'elles soient validées.

## Page Review (site, administrateurs seulement)

`/review` sur le site prend les mêmes décisions en un seul endroit : un onglet par type (demandes de compte,
sessions, logiciels, matériel, laboratoires, références, contacts, souches, profils d'animaux) avec le nombre en
attente, le plus ancien d'abord. Chaque élément peut être validé ou renvoyé avec une raison, un par un ou
plusieurs à la fois ; une demande de compte est activée ou rejetée (seule une demande toute neuve peut être
rejetée). Une session est validée avec tout ce qu'elle utilise. Le lien, avec le compteur, est dans le menu *Add*
de l'en-tête pour les administrateurs et un bouton *Review* dans leur profil ; à côté, *Check links* ouvre la
vérification des liens de téléchargement (voir [vérification des liens](link-check.md)). Elle utilise
`GET /api/review/`, `GET /api/review/<kind>/` et `POST /api/review/<kind>/decision/` (`{"action": "validate" |
"send_back", "ids": [...], "reason": "..."}`), réservés au personnel.
