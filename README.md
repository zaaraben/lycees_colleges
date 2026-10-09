# Typologie des lycées selon la valeur ajoutée

Application de cartographie des lycées de France (généraux, technologiques et
professionnels), classés selon leur **valeur ajoutée**, basée sur le
[mviewer](https://mviewer.netlify.app/).

Réalisée par **L'Observatoire citoyen** — [mesdonneeslocales.fr](https://mesdonneeslocales.fr).
Construite sur le même modèle que la carte « Densité carcérale ».

## La carte

- **Couleur** : typologie de valeur ajoutée (voir ci-dessous).
- **Taille** : nombre de candidats présentés au baccalauréat.
- **Fiche** : typologie, VA accès, VA réussite, taux de réussite, mention, accès, effectif.
- **Filtre** : par typologie, type de lycée (GT / pro) et secteur.

## La typologie (seuil ±4 points)

Croisement de deux valeurs ajoutées : la **VA accès** (mener les élèves de la
2ⁿᵈᵉ au bac) et la **VA réussite** (réussite à l'examen vs attendu).

| Catégorie | VA accès | VA réussite |
|---|---|---|
| 🟢 Performant | ≥ +4 | ≥ +4 |
| 🔵 Sélectif | < −4 | ≥ +4 |
| 🟠 Accompagnateur | ≥ +4 | < −4 |
| 🔴 En deçà des attentes | < −4 | < −4 |
| ⚪ Neutre | tous les autres cas | |
| ◻︎ Non disponible | valeur ajoutée non publiée | |

Session 2025 : **4 350 lycées** (2 341 GT, 2 009 pro). Répartition : 323 performants,
103 sélectifs, 47 accompagnateurs, 385 en deçà, 3 214 neutres, 278 non disponibles.

> Les **collèges** ne sont pas inclus : ils n'ont pas de valeur ajoutée sur
> l'accès (le second axe de la typologie).

## Données

Données ouvertes du ministère de l'Éducation nationale (DEPP), via
data.education.gouv.fr, jointes sur le code UAI. Voir
[`scripts/README.md`](scripts/README.md) pour le détail et la mise à jour.

## Structure

```
lycees_colleges.xml                      Configuration mviewer de l'application
lycees_colleges/
  css/theme.css                          Thème (identique aux autres cartes du site)
  customlayer/indicateurs.js             Couche OpenLayers (cercles colorés par typologie)
  data/lycees_colleges.json              Données de la carte (GeoJSON, EPSG:3857)
  data/lycees_colleges.meta.json         Suivi (session, sources, répartition)
  indicateurs.mst                        Gabarit de la fiche établissement
  filter/                                Plugin de filtre (typologie, type, secteur)
  legende_lycees_colleges.png            Légende
  help.html                              Aide
scripts/
  maj_lycees_colleges.py                 Mise à jour des données depuis l'API
  requirements.txt
  README.md
.github/workflows/maj-annuelle.yml       Mise à jour automatique
```

## Installation locale

Déposer le dossier dans l'arborescence mviewer (`apps/lycees_colleges/`) et
placer `lycees_colleges.xml` là où le mviewer lit ses configurations
d'application. La carte est alors accessible via
`…/mviewer/?config=apps/lycees_colleges/lycees_colleges.xml`.
