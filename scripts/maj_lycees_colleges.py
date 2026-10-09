#!/usr/bin/env python3
"""Mise à jour de la carte « Typologie des lycées selon la valeur ajoutée »
(mesdonneeslocales.fr).

Reconstruit le fichier chargé par la carte,
`lycees_colleges/data/lycees_colleges.json`, à partir de trois jeux de données
ouverts de data.education.gouv.fr (API Opendatasoft Explore v2.1) :

  - indicateurs de valeur ajoutée des lycées GT  (fr-en-indicateurs-de-resultat-des-lycees-gt_v2)
  - indicateurs de valeur ajoutée des lycées pro (fr-en-indicateurs-de-resultat-des-lycees-pro_v2)
  - adresse et géolocalisation des établissements (…premier-et-second-degre)

Les deux jeux d'indicateurs sont joints à la géolocalisation sur le code UAI.
Chaque lycée est classé dans une typologie à deux axes de valeur ajoutée
(seuil ±4 points) :

  - Performant           : VA accès ≥ +4 ET VA réussite ≥ +4
  - Sélectif             : VA accès < −4 ET VA réussite ≥ +4
  - Accompagnateur       : VA accès ≥ +4 ET VA réussite < −4
  - En deçà des attentes : VA accès < −4 ET VA réussite < −4
  - Neutre               : tous les autres cas
  - Non disponible       : valeur ajoutée non publiée

Les coordonnées WGS84 sont reprojetées en EPSG:3857.

Rendu : couleur = catégorie de typologie, taille = nombre de candidats.

Note : les collèges ne sont pas inclus (ils n'ont pas de valeur ajoutée sur
l'accès, le second axe de la typologie).

Exemples :
  python scripts/maj_lycees_colleges.py                 # dernière session publiée
  python scripts/maj_lycees_colleges.py --annee 2024    # une session précise

Codes de sortie :
  0  mise à jour effectuée (ou déjà à jour)
  1  erreur : API illisible, structure inattendue, trop peu d'établissements…
  3  session pas encore publiée

Aucune dépendance externe : uniquement la bibliothèque standard Python.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
APP = RACINE / "lycees_colleges"
SORTIE_GEOJSON = APP / "data" / "lycees_colleges.json"
SORTIE_META = APP / "data" / "lycees_colleges.meta.json"
FICHIER_XML = RACINE / "lycees_colleges.xml"

API = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"

DS_GEO = "fr-en-adresse-et-geolocalisation-etablissements-premier-et-second-degre"
DS_GT = "fr-en-indicateurs-de-resultat-des-lycees-gt_v2"
DS_PRO = "fr-en-indicateurs-de-resultat-des-lycees-pro_v2"

# Seuil de la typologie, en points de valeur ajoutée.
SEUIL_VA = 4

# En dessous de ce nombre d'établissements, on considère que l'API a changé.
NB_MIN_ATTENDU = 3500


class ErreurStructure(Exception):
    """Les données renvoyées par l'API n'ont pas la structure attendue."""


class SessionNonPubliee(Exception):
    """La session demandée n'est pas disponible dans un des jeux de données."""


# --------------------------------------------------------------------------
# Accès API
# --------------------------------------------------------------------------

def _lire_json(url: str, essais: int = 4, pause: int = 20):
    requete = urllib.request.Request(
        url, headers={"User-Agent": "mesdonneeslocales.fr (maj lycees)"}
    )
    for essai in range(1, essais + 1):
        try:
            with urllib.request.urlopen(requete, timeout=120) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404 or essai == essais:
                raise
            print(f"  -> HTTP {e.code}, nouvel essai dans {pause} s")
        except (urllib.error.URLError, TimeoutError) as e:
            if essai == essais:
                raise
            print(f"  -> réseau ({e}), nouvel essai dans {pause} s")
        time.sleep(pause)
    raise RuntimeError("inaccessible")


def exporter(dataset: str, select: str, where: str) -> list[dict]:
    """Récupère tous les enregistrements d'un jeu via l'endpoint /exports/json."""
    params = urllib.parse.urlencode({"select": select, "where": where})
    url = f"{API}{dataset}/exports/json?{params}"
    print(f"Export : {dataset}")
    data = _lire_json(url)
    if not isinstance(data, list):
        raise ErreurStructure(f"{dataset} : réponse inattendue (pas une liste).")
    print(f"  -> {len(data)} enregistrements")
    return data


def derniere_session(dataset: str, champ_annee: str = "annee") -> int:
    url = (f"{API}{dataset}/records?select={champ_annee}"
           f"&group_by={champ_annee}&order_by={champ_annee}%20desc&limit=1")
    j = _lire_json(url)
    res = j.get("results") or []
    if not res:
        raise ErreurStructure(f"{dataset} : impossible de lire les sessions.")
    m = re.search(r"(\d{4})", str(res[0][champ_annee]))
    if not m:
        raise ErreurStructure(f"{dataset} : session illisible.")
    return int(m.group(1))


# --------------------------------------------------------------------------
# Typologie, jointure et harmonisation
# --------------------------------------------------------------------------

def typologie(va_acces, va_reu) -> str:
    """Classe un lycée selon ses deux valeurs ajoutées (seuil ±SEUIL_VA)."""
    if va_acces is None or va_reu is None:
        return "Non disponible"
    if va_acces >= SEUIL_VA and va_reu >= SEUIL_VA:
        return "Performant"
    if va_acces < -SEUIL_VA and va_reu >= SEUIL_VA:
        return "Sélectif"
    if va_acces >= SEUIL_VA and va_reu < -SEUIL_VA:
        return "Accompagnateur"
    if va_acces < -SEUIL_VA and va_reu < -SEUIL_VA:
        return "En deçà des attentes"
    return "Neutre"


def to_merc(lon: float, lat: float) -> list[float]:
    R = 6378137.0
    x = R * math.radians(lon)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return [round(x, 4), round(y, 4)]


def inum(v):
    if v in ("", None):
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


def secteur_lib(s):
    if not s:
        return None
    t = str(s).lower()
    if t.startswith("pu") or t == "public":
        return "Public"
    if t.startswith("pr") or t.startswith("priv"):
        return "Privé"
    return s


def charger_geoloc() -> dict:
    rows = exporter(
        DS_GEO,
        "numero_uai,latitude,longitude,secteur_public_prive_libe,libelle_commune,"
        "code_departement,libelle_departement,libelle_academie",
        "latitude is not null and longitude is not null",
    )
    return {g["numero_uai"]: g for g in rows if g.get("numero_uai")}


SELECT_LYC = ("annee,uai,libelle_uai,secteur,libelle_commune,code_departement,"
              "libelle_departement,libelle_academie,presents_total,taux_reu_total,"
              "va_reu_total,va_acces_2nde,taux_men_total,taux_acces_2nde")


def construire_features(annee: int, geo: dict):
    where = f"annee=date'{annee}-01-01'"
    gt = exporter(DS_GT, SELECT_LYC, where)
    pro = exporter(DS_PRO, SELECT_LYC, where)
    for nom, rows in (("lycées GT", gt), ("lycées pro", pro)):
        if not rows:
            raise SessionNonPubliee(f"Aucune donnée {nom} pour la session {annee}.")

    feats = []
    sans_geo = {"Lycée GT": 0, "Lycée pro": 0}

    def ajouter(type_etab, r):
        g = geo.get(r.get("uai"))
        if not g:
            sans_geo[type_etab] += 1
            return
        va_acces = inum(r.get("va_acces_2nde"))
        va_reu = inum(r.get("va_reu_total"))
        lon, lat = g["longitude"], g["latitude"]
        i = len(feats) + 1
        feats.append({
            "type": "Feature", "id": f"etab.{i}",
            "geometry": {"type": "Point", "coordinates": to_merc(lon, lat)},
            "geometry_name": "geom",
            "properties": {
                "id": i, "uai": r.get("uai"), "etablissement": r.get("libelle_uai"),
                "type_etab": type_etab,
                "secteur": secteur_lib(r.get("secteur")) or secteur_lib(g.get("secteur_public_prive_libe")),
                "commune": r.get("libelle_commune") or g.get("libelle_commune"),
                "code_departement": r.get("code_departement"),
                "departement": r.get("libelle_departement") or g.get("libelle_departement"),
                "academie": r.get("libelle_academie") or g.get("libelle_academie"),
                "presents": inum(r.get("presents_total")),
                "taux_reussite": inum(r.get("taux_reu_total")),
                "va_reussite": va_reu, "va_acces": va_acces,
                "taux_mention": inum(r.get("taux_men_total")),
                "taux_acces": inum(r.get("taux_acces_2nde")),
                "typologie": typologie(va_acces, va_reu),
                "latitude": round(lat, 6), "longitude": round(lon, 6),
                "annee": str(r.get("annee") or annee),
            },
        })

    for r in gt:
        ajouter("Lycée GT", r)
    for r in pro:
        ajouter("Lycée pro", r)
    return feats, sans_geo


def verifier(feats: list[dict]) -> None:
    if len(feats) < NB_MIN_ATTENDU:
        raise ErreurStructure(
            f"Seulement {len(feats)} lycées construits (< {NB_MIN_ATTENDU}) : "
            "les champs ou la structure de l'API ont probablement changé."
        )
    for f in feats:
        x, y = f["geometry"]["coordinates"]
        if not (-20037508 <= x <= 20037508 and -20037508 <= y <= 20037508):
            raise ErreurStructure(f"Coordonnées hors emprise pour {f['properties']['etablissement']}")
        t = f["properties"]["taux_reussite"]
        if isinstance(t, (int, float)) and not (0 <= t <= 100):
            raise ErreurStructure(f"Taux de réussite improbable ({t}) pour {f['properties']['etablissement']}")


# --------------------------------------------------------------------------
# Écriture
# --------------------------------------------------------------------------

def maj_titre(annee: int) -> None:
    if not FICHIER_XML.exists():
        return
    texte = FICHIER_XML.read_text(encoding="utf-8")
    nouveau, n = re.subn(r"session \d{4}", f"session {annee}", texte)
    if n:
        FICHIER_XML.write_text(nouveau, encoding="utf-8")
    else:
        print(f"ATTENTION : titre non trouvé dans {FICHIER_XML.name}, non modifié.")


def deja_a_jour(annee: int) -> bool:
    if not SORTIE_META.exists():
        return False
    meta = json.loads(SORTIE_META.read_text(encoding="utf-8"))
    return str(meta.get("annee_donnees")) == str(annee)


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--annee", type=int, help="Session à charger (AAAA). Défaut : la plus récente.")
    parser.add_argument("--force", action="store_true", help="Retraiter même si déjà à jour.")
    args = parser.parse_args(argv)

    try:
        if args.annee:
            annee = args.annee
        else:
            annees = [derniere_session(DS_GT), derniere_session(DS_PRO)]
            annee = min(annees)
            print(f"Sessions disponibles GT/pro = {annees} -> session retenue {annee}")

        print(f"== Typologie des lycées (valeur ajoutée) — session {annee} ==")
        if not args.force and deja_a_jour(annee):
            print("Déjà à jour, rien à faire.")
            return 0

        geo = charger_geoloc()
        feats, sans_geo = construire_features(annee, geo)
        verifier(feats)
    except SessionNonPubliee as e:
        print(f"PAS ENCORE PUBLIÉ : {e}")
        return 3
    except ErreurStructure as e:
        print(f"ERREUR : {e}")
        return 1
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"ERREUR : accès API impossible ({e}).")
        return 1
    except Exception as e:
        print(f"ERREUR : {type(e).__name__} : {e}.")
        return 1

    from collections import Counter
    byt = Counter(f["properties"]["type_etab"] for f in feats)
    typo = Counter(f["properties"]["typologie"] for f in feats)
    print(f"Lycées sur la carte : {len(feats)} "
          f"(GT {byt['Lycée GT']}, pro {byt['Lycée pro']})")
    print(f"Répartition typologie : {dict(typo)}")
    total_sans_geo = sum(sans_geo.values())
    if total_sans_geo:
        print(f"Info : {total_sans_geo} lycée(s) sans géolocalisation : {dict(sans_geo)}")

    fc = {
        "type": "FeatureCollection", "features": feats,
        "totalFeatures": len(feats), "numberMatched": len(feats),
        "numberReturned": len(feats),
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}},
    }
    SORTIE_GEOJSON.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    maj_titre(annee)
    meta = {
        "annee_donnees": str(annee),
        "perimetre": "Lycées d'enseignement général, technologique et professionnel",
        "indicateur": "Typologie selon la valeur ajoutée "
                      f"(VA accès 2nde × VA réussite, seuil ±{SEUIL_VA} points)",
        "typologie_definition": {
            "Performant": f"VA accès >= +{SEUIL_VA} et VA réussite >= +{SEUIL_VA}",
            "Sélectif": f"VA accès < -{SEUIL_VA} et VA réussite >= +{SEUIL_VA}",
            "Accompagnateur": f"VA accès >= +{SEUIL_VA} et VA réussite < -{SEUIL_VA}",
            "En deçà des attentes": f"VA accès < -{SEUIL_VA} et VA réussite < -{SEUIL_VA}",
            "Neutre": "tous les autres cas",
            "Non disponible": "valeur ajoutée non publiée par la DEPP",
        },
        "sources": {
            "indicateurs_lycees_gt": f"https://data.education.gouv.fr/explore/dataset/{DS_GT}/",
            "indicateurs_lycees_pro": f"https://data.education.gouv.fr/explore/dataset/{DS_PRO}/",
            "geolocalisation": f"https://data.education.gouv.fr/explore/dataset/{DS_GEO}/",
        },
        "date_traitement": date.today().isoformat(),
        "nb_etablissements_carte": len(feats),
        "nb_lycees_gt": byt["Lycée GT"],
        "nb_lycees_pro": byt["Lycée pro"],
        "repartition_typologie": dict(typo),
        "etablissements_sans_geoloc": total_sans_geo,
    }
    SORTIE_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Écrit : {SORTIE_GEOJSON.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
