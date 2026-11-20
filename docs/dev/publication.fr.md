# Sessions publiées et versions

Une session publiée continue de vivre (la notice dans le dépôt est celle de sa session) :

- l'auteur peut la **modifier** ; la description et les mots-clés de sa notice dans le dépôt suivent, en arrière-plan
  (`update_published_record`), sans nouvelle version : la notice est déverrouillée, mise à jour et republiée avec le
  même DOI. L'état est montré sur la session (`zenodo_state` : à jour, en cours, en attente, échec). Si la
  modification lui fait utiliser des fiches que personne n'a encore validées, la mise à jour attend leur validation
  (`blocked`) et s'exécute toute seule quand un administrateur les valide, si bien que le public ne lit jamais
  rien sur une fiche non validée. Deux modifications de suite ne mettent jamais la notice à jour en même temps (une
  mise à jour par session, la suivante attend), et un dépôt injoignable ou qui répond 5xx/429 est réessayé avec un
  délai croissant (l'état reste `pending` ; un refus est `failed` tout de suite)
- l'auteur peut **ajouter des fichiers** : ils vont dans le brouillon d'une **nouvelle version** de la notice (le
  brouillon contient les fichiers de la version précédente) ; *Publish a new version* la publie. Chaque version a son
  propre DOI (`PublicationVersion`), le DOI de l'ensemble est `concept_doi` ; un fichier d'une version publiée ne
  peut être retiré par personne (administrateurs compris : le dépôt refuserait), un fichier en attente de la
  prochaine version le peut
- l'auteur peut demander d'**envoyer les tableaux des outils de détection et les images d'un fichier**
  (spectrogramme, courbe) avec la notice : une case sur chacun, décochée par défaut (voir
  [détections](usv-detections.md) et [jeux de données](datasets.md)). Ils sont mis dans le brouillon juste avant sa
  publication (la première publication et chaque nouvelle version), nommés comme le fichier
  (`<file>_<tool>.csv`, `<file>_spectrogram.png`, `<file>_plot.png`), et seulement pour les fichiers que mouseTube a
  lui-même envoyés à cette notice. Ce qui est coché après la publication d'une notice part avec la version suivante ;
  modifier la description ne l'envoie pas
- cela ne fonctionne que pour les notices que mouseTube a publiées lui-même : une session importée avec le DOI d'une
  notice faite ailleurs n'a pas de version à suivre

## Publication après validation

Une session qui utilise des fiches que personne n'a encore validées attend un administrateur (voir
[modération](moderation.md)). Son auteur peut demander, avec la case *Publish automatically once validated* à côté
de *Share this session*, qu'elle soit publiée toute seule une fois partagée. Cela ne compte que quand la session
doit attendre : une session partagée tout de suite est publiée avec son propre bouton.

1. La session passe en *waiting validation* et l'aperçu de la publication s'ouvre (le même que le bouton
   *Publish* : titre, description, mots-clés, personnes, licence). L'auteur le relit, le modifie s'il veut, et
   l'approuve (`POST /api/recording-session/<id>/auto-publish/` avec `repository_id` et le `payload` ; seulement
   l'auteur, seulement pendant que la session attend). Fermer l'aperçu sans approuver veut dire pas de publication
   automatique.
2. Quand un administrateur valide la session (la page Review, l'action de l'admin, ou en validant la dernière fiche
   qu'elle attendait), les métadonnées qui seraient publiées maintenant sont comparées à celles que l'auteur a
   regardées (une empreinte gardée à l'approbation). **Si elles sont identiques**, la session est publiée comme
   approuvée (tâche `auto_publish_session`) et l'auteur reçoit un e-mail avec le DOI. **Si elles ont changé** (un
   administrateur a corrigé quelque chose entre-temps), rien ne part : l'état devient `stale`, l'auteur est prévenu,
   et publie à la main avec un nouvel aperçu.
3. Un échec (le dépôt est occupé, un fichier manque...) laisse la session partagée, avec l'état `failed` et la
   raison, et l'auteur est prévenu par e-mail : il peut publier depuis la page de la session.

`auto_publish_state` (`approved`, `stale`, `publishing`, `done`, `failed`) et `auto_publish_message` sont montrés
avec la session ; les métadonnées approuvées elles-mêmes ne sont jamais renvoyées à la page. Retirer la demande, ou
*Cancel automatic publication* (`DELETE` sur la même route), supprime l'approbation. Le worker Celery doit être
redémarré pour la nouvelle tâche (voir [mettre à jour un déploiement](deployment.md)).
