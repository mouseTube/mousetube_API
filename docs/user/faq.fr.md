# FAQ et glossaire

## Questions

??? question "Faut-il un compte pour télécharger des enregistrements ?"
    Non. Parcourir, chercher et télécharger est ouvert à tous. Il faut un compte pour ajouter des données.

??? question "Pourquoi ne puis-je pas m'inscrire avec mon adresse Gmail ?"
    mouseTube demande une adresse e-mail **institutionnelle** (université, institut de recherche, hôpital) parce
    qu'un administrateur vérifie que les données viennent de chercheurs. Utilisez votre adresse professionnelle.

??? question "J'ai confirmé mon e-mail mais je ne peux toujours pas me connecter."
    Un administrateur doit activer votre compte. Vous êtes prévenu par e-mail. La page de connexion vous dit
    aussi où en est votre demande.

??? question "Pourquoi ma session n'est-elle pas publique après que je l'ai partagée ?"
    Elle utilise quelque chose que personne n'a encore validé, donc elle **attend la validation** et reste privée.
    La carte Visibility liste ce qui attend. Voir [Partage et validation](share.md).

??? question "Je ne peux pas modifier ma session."
    Une session **en attente de validation** est verrouillée pendant qu'un administrateur la lit. **Withdraw** la
    depuis *My vocalizations*, modifiez-la, puis partagez-la à nouveau. Une session partagée ou publiée n'est pas
    verrouillée.

??? question "Je ne peux pas modifier un laboratoire, une souche ou un matériel que j'ai créé."
    Une fois qu'un administrateur l'a **validé**, il est partagé par tous et verrouillé. Demandez à un
    administrateur de le corriger.

??? question "Un microphone que j'ai ajouté n'apparaît pas sur ma session publique."
    Il n'est pas encore validé : il est caché aux autres (vous le voyez toujours) jusqu'à ce qu'un administrateur
    le valide.

??? question "Où sont stockés les fichiers audio ?"
    Dans un **dépôt**, le plus souvent Zenodo. mouseTube garde la description et les liens. Utilisez le bouton
    Download ou le DOI.

??? question "Puis-je mettre mes fichiers ailleurs et seulement les décrire sur mouseTube ?"
    Oui. Donnez le **lien de téléchargement** et le **DOI** du fichier quand vous l'ajoutez : mouseTube les
    enregistre sans rien déposer.

??? question "Comment citer mes données ?"
    Publiez la session pour obtenir un **DOI**, puis citez-le comme n'importe quel jeu de données. Voir
    [Publier avec un DOI](publish.md).

??? question "Puis-je utiliser mouseTube depuis un programme ?"
    Oui, avec l'API REST. Voir la [documentation développeur](../dev/api/index.md).

## Glossaire

<dl>
<dt>Profil d'animaux</dt><dd>Le type d'animaux enregistrés : souche, sexe, âge, génotype, traitement et régime.</dd>
<dt>Vocabulaire contrôlé / ontologie</dt><dd>Une liste de termes de référence avec un identifiant (par exemple <code>EFO:0000606</code> pour la souche C57BL/6J) pour que tout le monde nomme les choses de la même façon. mouseTube vérifie les termes à leur source.</dd>
<dt>Jeu de données</dt><dd>Une collection choisie de sessions avec ses métadonnées.</dd>
<dt>Brouillon</dt><dd>Travail en cours, privé, vu seulement de son auteur.</dd>
<dt>DOI</dt><dd>Digital Object Identifier : un lien permanent vers un dépôt, à citer.</dd>
<dt>Protocole</dt><dd>Comment l'enregistrement a été organisé, écrit sous forme d'un code construit à partir de ses champs.</dd>
<dt>Publié</dt><dd>Partagé et déposé dans un dépôt, avec un DOI.</dd>
<dt>Session d'enregistrement</dt><dd>Un ensemble d'enregistrements faits dans les mêmes conditions expérimentales.</dd>
<dt>Dépôt</dt><dd>Un service qui stocke les fichiers et leur donne un DOI (Zenodo).</dd>
<dt>Partagé</dt><dd>Public, lisible par tous.</dd>
<dt>USV</dt><dd>Vocalisation ultrasonique : un appel au-dessus de ce que l'oreille humaine entend, émis par les rongeurs.</dd>
<dt>Validé</dt><dd>Vérifié par un administrateur de mouseTube. Seules les fiches validées sont montrées à tous.</dd>
<dt>En attente de validation</dt><dd>Envoyé en relecture : privé et verrouillé jusqu'à la décision d'un administrateur.</dd>
</dl>
