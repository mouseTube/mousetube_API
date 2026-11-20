# Mettre à jour un déploiement

Les deux dépôts (`mousetube_API` et `mousetube_frontend`) vont ensemble : déployez-les en même temps. Un ancien
site ne fonctionne pas avec cette API (format d'inscription, route du compteur de téléchargements, format des
statuts, et un jeton d'accès qui dure maintenant une heure et est renouvelé par le nouveau site).

1. Récupérez le nouveau code dans les deux dossiers (`git pull`), puis reconstruisez : `docker compose -f docker-compose.prod.yml up -d --build`
   (`update.sh` fait le pull, la construction et un nettoyage).
2. **Redémarrez le worker Celery** si vous ne reconstruisez pas : il ne recharge pas son code, et un worker périmé
   échoue sur les nouveaux modèles et tâches.
3. Les migrations sont versionnées (`mousetube_api/migrations/`) : le conteneur `web` les applique à son démarrage
   (`migrate`) ; il n'en génère jamais. Après un changement des modèles, lancez `python manage.py makemigrations`,
   relisez le fichier et committez-le (un test échoue quand un modèle a changé sans sa migration). Les conversions de
   lignes existantes sont faites par `python manage.py normalize_data`, que l'entrypoint lance après `migrate` et
   qui est sans risque à relancer (lancez-le à la main si le conteneur est démarré sans l'entrypoint).
4. Réglez `DRF_NUM_PROXIES` au nombre de proxys inverses (nginx, HAProxy) : avec `0`, chaque visiteur partage une
   adresse et les limites de débit s'appliquent à tout le site. Le conteneur avertit au démarrage quand c'est `0`
   hors debug.
5. `DEBUG` vaut faux par défaut : un environnement de développement a besoin d'un `.env` (voir `.env.example`).
   `RESET_DB=true` est refusé sauf si `DEBUG=true`. En production, le conteneur du site a besoin de `DEBUG=false` ou
   d'aucun `DEBUG`, jamais `true`.
6. Faites un dump de la base avant une grosse mise à jour (`docker compose exec db mariadb-dump ...`).
7. Reconstruisez l'image quand une dépendance est ajoutée (`defusedxml` lit les tableaux des outils de détection) ;
   `--build` le fait. Le worker Celery doit connaître les tâches de la nouvelle version (la vérification des liens en
   est une).
8. Les tableaux que les auteurs ont choisi d'envoyer à Zenodo sont gardés dans `media/usv_results/` jusqu'à leur
   publication : incluez `media/` dans les sauvegardes.
9. La version de l'API est celle de `pyproject.toml` (la documentation et `GET /api/version/` la donnent) ; celle du
   site est dans son `package.json`. Le pied de page du site affiche les deux.
