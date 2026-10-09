# Mise à jour des données — collèges et lycées

Le script `maj_lycees_colleges.py` reconstruit le fichier chargé par la carte,
`lycees_colleges/data/lycees_colleges.json`, à partir de l'API Opendatasoft de
data.education.gouv.fr.

## Sources (data.education.gouv.fr)

| Jeu de données | Dataset |
|---|---|
| Indicateurs de valeur ajoutée des lycées GT | `fr-en-indicateurs-de-resultat-des-lycees-gt_v2` |
| Indicateurs de valeur ajoutée des lycées pro | `fr-en-indicateurs-de-resultat-des-lycees-pro_v2` |
| Indicateurs de valeur ajoutée des collèges | `fr-en-indicateurs-valeur-ajoutee-colleges` |
| Adresse et géolocalisation des établissements | `fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre` |

La jointure se fait sur le **code UAI** (`uai` ↔ `numero_uai`). Les coordonnées
WGS84 de la géolocalisation sont reprojetées en **EPSG:3857**.

## Installation

Aucune dépendance externe (bibliothèque standard Python uniquement) :

```bash
# rien à installer ; Python 3.9+ suffit
pip install -r scripts/requirements.txt   # optionnel, ne fait rien
```

## Utilisation

Depuis la racine du dépôt :

```bash
# Dernière session publiée (commune aux trois jeux)
python scripts/maj_lycees_colleges.py

# Une session précise
python scripts/maj_lycees_colleges.py --annee 2024

# Forcer le retraitement d'une session déjà écrite
python scripts/maj_lycees_colleges.py --annee 2025 --force
```

## Ce que le script modifie

- `lycees_colleges/data/lycees_colleges.json` : les données de la carte
- `lycees_colleges.xml` : le titre (« … session 2025 »)
- `lycees_colleges/data/lycees_colleges.meta.json` : le suivi (session, sources,
  nombre d'établissements par type, établissements sans géolocalisation)

## Contrôles automatiques

Le script s'arrête sans rien modifier si :

- un des trois jeux ne renvoie aucune donnée pour la session (code 3) ;
- moins de 8 000 établissements sont construits (signe d'un changement de
  champs ou de structure de l'API) ;
- une coordonnée sort de l'emprise EPSG:3857 ou un taux de réussite est hors
  de l'intervalle 0–100.

## Harmonisation des indicateurs

| Champ carte | Lycées GT / pro | Collèges |
|---|---|---|
| `taux_reussite` | `taux_reu_total` | `taux_de_reussite_g` (DNB, général) |
| `va_reussite` | `va_reu_total` | `va_du_taux_de_reussite_g` |
| `taux_mention` | `taux_men_total` | calculé : `nb_mentions_global_g / nb_candidats_g` |
| `taux_acces` | `taux_acces_2nde` | `taux_d_acces_6eme_3eme` |
| `presents` | `presents_total` | `nb_candidats_g` |

## Codes de sortie

| Code | Signification |
|---|---|
| 0 | Mise à jour effectuée, ou déjà à jour |
| 1 | Erreur (API, structure…) |
| 3 | Session pas encore publiée |

## Automatisation

Le workflow `.github/workflows/maj-annuelle.yml` lance ce script une fois par
mois : dès qu'une nouvelle session est publiée (en général à l'automne), les
données sont mises à jour et enregistrées dans le dépôt. Il peut aussi être
lancé à la main depuis l'onglet **Actions** (« Run workflow »), avec une année
précise.
