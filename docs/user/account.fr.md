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
