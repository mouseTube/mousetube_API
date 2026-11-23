# Détections de vocalisations ultrasonores

Un fichier peut venir avec les résultats des outils de détection qui ont été lancés dessus : les appels que chaque
outil a trouvés, montrés dans la liste des vocalisations à côté de l'enregistrement. mouseTube ne lance aucun
détecteur : l'auteur lance l'outil et donne son tableau, mouseTube le lit et le montre. Les outils ne s'accordent pas
entre eux, donc chacun est montré avec ses propres chiffres et chaque variable qu'il a écrite, et chacun choisit
celui en qui il a confiance.

## Les outils

| Outil | Tableau |
|---|---|
| USVSEG | `.csv`, `.txt` |
| DeepSqueak | `.xlsx`, `.csv` |
| Avisoft SASLab Pro | `.csv`, `.txt` |
| SonoTrack | `.txt`, `.csv` |
| RatRec | `.csv`, `.txt` |
| LMT USV Toolbox | `.csv` |

`GET /api/usv-detection/tools/` les liste avec leur couleur, leurs formats et leur publication. Un outil s'ajoute
dans `mousetube_api/utils/usv.py` : une entrée dans `TOOLS` et une description de ses colonnes dans `READERS`
(quelles colonnes portent le début et la fin, dans quelle unité, et les fréquences).

## Ce que fait l'auteur

Dans le formulaire qui ajoute un fichier **audio**, une carte par outil reçoit son tableau. Le serveur le lit tout
de suite et le formulaire montre un aperçu (appels, cadence, une frise, le tableau) de ce que les gens verront ; rien
n'est enregistré à ce moment-là (`POST /api/usv-detection/preview/`). Les tableaux sont attachés quand le fichier
est créé (`POST /api/file/<id>/usv-detections/`, le créateur du fichier seulement ; renvoyer un outil remplace son
résultat). Le créateur peut retirer un résultat (`DELETE /api/usv-detection/<id>/`).

## Ce qui est gardé

Une ligne par fichier et par outil (`UsvDetection`) : l'outil, sa version et ses réglages quand ils sont connus, un
résumé (nombre d'appels, cadence, durée médiane, fréquences) et les appels. Chaque appel a les mêmes quelques
colonnes quel que soit l'outil (début et fin en secondes, fréquence minimale, maximale, moyenne et de pic en kHz) et,
dans `native`, toutes les variables que l'outil a données, intactes. Un chemin de l'ordinateur de l'auteur
(DeepSqueak en écrit un) est réduit au nom du fichier.

La liste des fichiers donne les résumés ; les appels sont lus quand quelqu'un ouvre un résultat
(`GET /api/usv-detection/<id>/`). Les résultats suivent la visibilité de leur fichier.

Limites : un tableau de 20 Mo au plus, 50 000 appels au plus, l'extension de l'outil ; un `.xlsx` est lu avec
`defusedxml` et refusé s'il se décompresse en plus de 100 Mo.

## Envoyer les tableaux au dépôt

Le tableau de l'auteur n'est **pas** envoyé à Zenodo sauf si l'auteur coche *Also send this table to Zenodo with
the recording* (décoché par défaut). Alors seulement le tableau d'origine est gardé sur le serveur
(`media/usv_results/`), et mis dans le brouillon de la notice juste avant sa publication, nommé
`<file>_<tool>.<ext>` (voir [sessions publiées](publication.md)). Sinon le tableau est lu, ses valeurs sont gardées
dans la base, et le fichier est jeté.

## Importer des résultats publiés

`python manage.py import_usv_detections --dir DIR` relie des résultats à des fichiers qui existent déjà. `DIR` a un
dossier par enregistrement, nommé comme le fichier sans `.wav`, contenant les résultats (`usvseg.csv`,
`deepsqueak.xlsx`, `avisoft.csv`, `sonotrack.txt`, `ratrec.csv`, `usvtoolbox.csv`) et, s'il y en a un,
`parameters_analysis.csv` (`label;settings` par outil, pour la version et les réglages). Options :
`--tools usvseg,deepsqueak` pour en prendre certains, `--created-by USERNAME`, `--dry-run`. Le relancer remplace les
mêmes résultats.
