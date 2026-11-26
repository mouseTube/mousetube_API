# Votre compte

Ouvrez l'icône de personne dans la barre du haut pour accéder à votre compte.

<figure markdown>
  ![La page du compte : profil avec nom, laboratoire et ORCID, et les onglets Preferences, My vocalizations, My hardware, My software et API token](../assets/img/account.png)
  <figcaption>Votre compte, avec le nombre de vos éléments sur chaque onglet.</figcaption>
</figure>

| Onglet | À quoi il sert |
|---|---|
| **Profile** | Votre nom, votre laboratoire (choisissez-en un, ou créez-le) et votre ORCID. **Link my ORCID** relie votre ORCID iD. |
| **Preferences** | Montrer votre e-mail à côté de vos enregistrements (désactivé par défaut), et l'affichage des listes (cartes ou tableau). |
| **My vocalizations** | Vos sessions par état, avec les actions qui conviennent à chacune. Voir [Partage et validation](share.md). |
| **My hardware**, **My software** | Le matériel et les logiciels que vous avez créés, avec leur état (brouillon, en attente, validé). |
| **API token** | Une clé personnelle pour des scripts. Voir ci-dessous. |

## Changer son mot de passe

Sur la page de votre compte, dans l'onglet **Preferences**, la section **Password** le change : saisissez votre **mot de passe
actuel**, puis le nouveau deux fois. Le nouveau mot de passe suit les règles du formulaire d'inscription : au moins 8
caractères, pas uniquement des chiffres, pas un mot de passe courant. Il ne demande pas de mail. Si vous l'avez
**oublié**, utilisez *Forgot your password?* sur la page de connexion : vous recevez un lien par e-mail.

## Supprimer votre compte

Dans l'onglet **Preferences**, la section **Delete my account** ouvre un mail vers `mousetube@igbmc.fr`, déjà rédigé
avec votre identifiant et l'adresse de votre compte. Envoyez-le depuis cette adresse. Un administrateur supprime le
compte et répond sous un mois. Votre profil et votre connexion sont supprimés ; les enregistrements et descriptions que
vous avez ajoutés restent sur mouseTube, sans lien avec votre compte, et ce qui a été publié sur Zenodo y reste public.

## Favoris

Marquez des protocoles, du matériel, des logiciels, des profils d'animaux, des souches, des laboratoires, des
références ou des contacts comme **favoris** : ils passent en premier dans les listes où vous choisissez. Les
favoris sont personnels.

## Le jeton d'API

L'onglet **API token** donne un **jeton d'accès** personnel : il permet à un programme d'agir comme **vous** sur
l'API de mouseTube. Il est réservé aux développeurs ; voir l'[API REST](../dev/api/index.md).

!!! danger "Gardez-le secret"
    Quiconque a votre jeton peut agir en votre nom. Ne le mettez jamais dans du code que d'autres peuvent lire. Il
    cesse de fonctionner au bout d'une heure, et vous pouvez en obtenir un nouveau.
