/**
 * Couche personnalisée mviewer — Typologie des lycées selon la valeur ajoutée
 *
 * Données : indicateurs de valeur ajoutée des lycées GT et professionnels
 * (DEPP), joints à la géolocalisation des établissements, via
 * data.education.gouv.fr.
 *
 * Typologie (deux axes de valeur ajoutée, seuil ±4 points) :
 *   - Performant           : VA accès ≥ +4 ET VA réussite ≥ +4
 *   - Sélectif             : VA accès < −4 ET VA réussite ≥ +4
 *   - Accompagnateur       : VA accès ≥ +4 ET VA réussite < −4
 *   - En deçà des attentes : VA accès < −4 ET VA réussite < −4
 *   - Neutre               : tous les autres cas
 *   - Non disponible       : valeur ajoutée non publiée (losange gris)
 *
 * Rendu (sur le modèle de la carte « Densité carcérale ») :
 *   - couleur selon la catégorie de typologie ;
 *   - cercle proportionnel au nombre de candidats présentés à l'examen.
 */

const LAYER_URL = (function () {
    var base = window.location.href.split('?')[0].replace(/\/[^/]*$/, '');
    return base + '/apps/lycees_colleges/data/lycees_colleges.json';
})();
const LAYER_ID = "indicateurs";

// Rayon : racine carrée de l'effectif (surface ~ effectif)
const MAX_VALUE = 500;
const MAX_RADIUS = 20;
const MIN_RADIUS = 4.5;

// Couleurs de la typologie
const COULEURS = {
    "Performant":            'rgba(26, 152, 80, 0.9)',    // vert
    "Sélectif":              'rgba(44, 127, 184, 0.9)',   // bleu
    "Accompagnateur":        'rgba(224, 130, 20, 0.9)',   // orange
    "En deçà des attentes":  'rgba(215, 48, 39, 0.9)',    // rouge
    "Neutre":                'rgba(189, 189, 189, 0.85)'  // gris
};
const COULEUR_ND = 'rgba(158, 158, 158, 0.75)';          // Non disponible

function isValidNumber(v) {
    return v !== null && v !== undefined && v !== "" && v !== 'NC' && !isNaN(Number(v));
}

function getRadius(presents) {
    if (!isValidNumber(presents)) return MIN_RADIUS;
    return Math.max(MIN_RADIUS, Math.sqrt(Number(presents) / MAX_VALUE) * MAX_RADIUS);
}

// Style « non disponible » : losange gris
function styleND(r) {
    return [new ol.style.Style({
        image: new ol.style.RegularShape({
            points: 4,
            angle: Math.PI / 4,
            radius: r,
            fill: new ol.style.Fill({ color: COULEUR_ND }),
            stroke: new ol.style.Stroke({ color: 'white', width: 1.5 })
        })
    })];
}

// Cercle proportionnel coloré
function styleCercle(r, color) {
    return [new ol.style.Style({
        image: new ol.style.Circle({
            radius: r,
            fill: new ol.style.Fill({ color: color }),
            stroke: new ol.style.Stroke({ color: 'white', width: 1.5 })
        })
    })];
}

function getStyle(feature) {
    var p = feature.getProperties();
    var cat = p.typologie;
    var r = getRadius(p.presents);
    if (!cat || cat === "Non disponible" || !(cat in COULEURS)) {
        return styleND(r);
    }
    return styleCercle(r, COULEURS[cat]);
}

let layer = new ol.layer.Vector({
    source: new ol.source.Vector({
        url: LAYER_URL,
        format: new ol.format.GeoJSON()
    }),
    style: getStyle
});

// Légende associée à la couche (image)
var legend = "apps/lycees_colleges/legende_lycees_colleges.png";

var indicateurs = new CustomLayer(LAYER_ID, layer, legend);
