// Donnees partagees : un flux d'evenements du serveur (Server-Sent Events) tient a jour les taches, les runs,
// les mesures du poste, les generations et la sortie des taches. A chaque reconnexion, tout est relu.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { enc, lire } from './api.js';

const HISTORIQUE = 900;
const HISTORIQUE_S = 1800; // trente minutes de mesures du poste
const JOURNAL_MAX = 400000;
const Contexte = createContext(null);

class Magasin {
  constructor() {
    this.valeurs = new Map();
    this.ecouteurs = new Map();
  }
  lire(cle) {
    return this.valeurs.get(cle);
  }
  ecrire(cle, valeur) {
    this.valeurs.set(cle, valeur);
    for (const f of this.ecouteurs.get(cle) ?? []) f();
  }
  ecouter(cle, f) {
    if (!this.ecouteurs.has(cle)) this.ecouteurs.set(cle, new Set());
    this.ecouteurs.get(cle).add(f);
    return () => this.ecouteurs.get(cle).delete(f);
  }
}

// --- Generations d'un run ---

const generations = new Magasin();
const chargements = new Map();
const tampons = new Map();

function chargerGenerations(run) {
  if (chargements.has(run)) return;
  tampons.set(run, []);
  const promesse = lire(`/api/runs/${enc(run)}/generations`)
    .then(lignes => {
      const derniere = lignes.length ? lignes[lignes.length - 1].generation : -1;
      const suite = (tampons.get(run) ?? []).filter(l => l.generation > derniere);
      generations.ecrire(run, { lignes: [...lignes, ...suite], charge: true });
    })
    .catch(e => generations.ecrire(run, { lignes: generations.lire(run)?.lignes ?? [], charge: true, erreur: e.message }))
    .finally(() => {
      chargements.delete(run);
      tampons.delete(run);
    });
  chargements.set(run, promesse);
}

function recevoirGenerations({ run, lignes, reinitialiser }) {
  if (reinitialiser) {
    if (generations.lire(run)) chargerGenerations(run);
    return;
  }
  if (chargements.has(run)) {
    tampons.get(run).push(...lignes);
    return;
  }
  const actuel = generations.lire(run);
  if (!actuel) return; // personne ne regarde ce run : il sera lu en entier a la demande
  const derniere = actuel.lignes.length ? actuel.lignes[actuel.lignes.length - 1].generation : -1;
  const nouvelles = lignes.filter(l => l.generation > derniere);
  if (nouvelles.length) generations.ecrire(run, { ...actuel, lignes: [...actuel.lignes, ...nouvelles] });
}

export function useGenerations(run) {
  const abonner = useCallback(f => (run ? generations.ecouter(run, f) : () => {}), [run]);
  const etat = useSyncExternalStore(abonner, () => (run ? generations.lire(run) : undefined));
  useEffect(() => {
    if (run && !generations.lire(run)) chargerGenerations(run);
  }, [run]);
  return etat ?? { lignes: [], charge: false };
}

// --- Sortie d'une tache ---

const journaux = new Magasin();

function rogner(texte) {
  if (texte.length <= JOURNAL_MAX) return texte;
  const coupe = texte.indexOf('\n', texte.length - JOURNAL_MAX);
  return texte.slice(coupe + 1);
}

function chargerJournal(id, depuis) {
  const url = `/api/taches/${enc(id)}/journal` + (depuis != null ? `?depuis=${depuis}` : '');
  return lire(url)
    .then(({ texte, position }) => {
      const actuel = journaux.lire(id);
      const base = depuis != null && actuel ? actuel.texte : '';
      journaux.ecrire(id, { texte: rogner(base + texte), position, charge: true });
    })
    .catch(() => journaux.ecrire(id, { texte: '', position: 0, charge: true }));
}

function recevoirJournal({ id, debut, texte, position }) {
  const actuel = journaux.lire(id);
  if (!actuel || position <= actuel.position) return;
  if (debut === actuel.position) journaux.ecrire(id, { ...actuel, texte: rogner(actuel.texte + texte), position });
  else chargerJournal(id, actuel.position); // un evenement manque : relire la suite
}

export function useJournal(id) {
  const abonner = useCallback(f => (id ? journaux.ecouter(id, f) : () => {}), [id]);
  const etat = useSyncExternalStore(abonner, () => (id ? journaux.lire(id) : undefined));
  useEffect(() => {
    if (id && !journaux.lire(id)) chargerJournal(id);
  }, [id]);
  return etat ?? { texte: '', position: 0, charge: false };
}

// --- Mesures du poste ---
// Hors du contexte : une mesure arrive toutes les deux secondes, et seules les vues du poste la lisent. Dans le
// contexte, elle ferait redessiner toute l'application a chaque fois.

const poste = new Magasin();
poste.ecrire('mesures', []);
const abonnerPoste = f => poste.ecouter('mesures', f);
const lirePoste = () => poste.lire('mesures');

function recevoirMesure(echantillon) {
  const h = lirePoste();
  poste.ecrire('mesures', [...h.slice(-(HISTORIQUE - 1)), echantillon].filter(x => x.t >= echantillon.t - HISTORIQUE_S));
}

export function useSysteme() {
  return useSyncExternalStore(abonnerPoste, lirePoste);
}

// --- Fournisseur ---

function lirePreference(cle, defaut) {
  try {
    return localStorage.getItem(cle) || defaut;
  } catch {
    return defaut;
  }
}

function ecrirePreference(cle, valeur) {
  try {
    localStorage.setItem(cle, valeur);
  } catch {
    /* stockage indisponible : la preference vaut pour cette page */
  }
}

export function Donnees({ children }) {
  const [taches, setTachesEtat] = useState([]);
  const [runs, setRunsEtat] = useState([]);
  const [connecte, setConnecte] = useState(false);
  const [decalage, setDecalage] = useState(0);
  const [racine, setRacine] = useState(null);
  const [effets, setEffetsEtat] = useState(() => lirePreference('effets', 'auto'));
  const [notifications, setNotificationsEtat] = useState(() => lirePreference('notifications', 'non'));
  // Listes deja recues du serveur : avant, une liste vide veut dire « pas encore lue », pas « vide ».
  const [pret, setPret] = useState({ taches: false, runs: false });
  const setTaches = useCallback(t => {
    setTachesEtat(t);
    setPret(p => (p.taches ? p : { ...p, taches: true }));
  }, []);
  const setRuns = useCallback(r => {
    setRunsEtat(r);
    setPret(p => (p.runs ? p : { ...p, runs: true }));
  }, []);

  const rafraichir = useCallback(() => {
    lire('/api/etat')
      .then(e => {
        setDecalage(new Date(e.maintenant).getTime() - Date.now());
        setRacine({ racine: e.racine, python: e.python });
      })
      .catch(() => {});
    lire('/api/taches').then(setTaches).catch(() => {});
    lire('/api/runs').then(setRuns).catch(() => {});
    lire('/api/systeme')
      .then(m => poste.ecrire('mesures', m))
      .catch(() => {});
    for (const run of generations.valeurs.keys()) chargerGenerations(run);
    for (const [id, j] of journaux.valeurs) chargerJournal(id, j.position);
  }, [setTaches, setRuns]);

  // Un flux ouvert tient une connexion au serveur tant que la page vit. Un onglet cache ferme le sien : le
  // navigateur n'en accorde que six par hote, et des onglets oublies bloqueraient toutes les requetes. Seul un
  // onglet qui doit notifier en arriere-plan garde le sien.
  useEffect(() => {
    let source = null;
    const ouvrir = () => {
      if (source) return;
      source = new EventSource('/api/flux');
      source.onopen = () => {
        setConnecte(true);
        rafraichir();
      };
      source.onerror = () => setConnecte(false);
      source.addEventListener('taches', e => setTaches(JSON.parse(e.data)));
      source.addEventListener('runs', e => setRuns(JSON.parse(e.data)));
      source.addEventListener('systeme', e => recevoirMesure(JSON.parse(e.data)));
      source.addEventListener('journal', e => recevoirJournal(JSON.parse(e.data)));
      source.addEventListener('generations', e => recevoirGenerations(JSON.parse(e.data)));
    };
    const fermer = () => {
      source?.close();
      source = null;
      setConnecte(false);
    };
    const suivre = () => (document.visibilityState === 'hidden' && notifications !== 'oui' ? fermer() : ouvrir());
    suivre();
    document.addEventListener('visibilitychange', suivre);
    return () => {
      document.removeEventListener('visibilitychange', suivre);
      fermer();
    };
  }, [rafraichir, notifications, setTaches, setRuns]);

  const setEffets = useCallback(valeur => {
    setEffetsEtat(valeur);
    ecrirePreference('effets', valeur);
  }, []);
  const setNotifications = useCallback(valeur => {
    setNotificationsEtat(valeur);
    ecrirePreference('notifications', valeur);
  }, []);

  const valeur = useMemo(() => {
    const tache = taches.find(t => t.etat === 'en cours' || t.etat === 'arret demande') ?? null;
    return { taches, tache, runs, connecte, decalage, racine, effets, setEffets, notifications, setNotifications, pret, rafraichir };
  }, [taches, runs, connecte, decalage, racine, effets, setEffets, notifications, setNotifications, pret, rafraichir]);

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useDonnees() {
  return useContext(Contexte);
}

// Instant du serveur, en secondes, mis a jour chaque seconde : les durees ne dependent pas de l'horloge du poste.
export function useMaintenant(periode = 1000) {
  const { decalage } = useDonnees();
  const [t, setT] = useState(() => Date.now() + decalage);
  useEffect(() => {
    setT(Date.now() + decalage);
    const minuterie = setInterval(() => setT(Date.now() + decalage), periode);
    return () => clearInterval(minuterie);
  }, [decalage, periode]);
  return t / 1000;
}

// Les fonds animes prennent de la GPU : en mode auto, ils s'eteignent pendant une tache.
export function useEffetsActifs() {
  const { tache, effets } = useDonnees();
  const reduit = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  return !reduit && (effets === 'oui' || (effets === 'auto' && !tache));
}

// Vrai au bout de ms millisecondes : un effet WebGL monte apres la transition de page, dont il ferait saccader
// l'animation en compilant ses shaders.
export function useDiffere(ms = 450) {
  const [pret, setPret] = useState(false);
  useEffect(() => {
    const minuterie = setTimeout(() => setPret(true), ms);
    return () => clearTimeout(minuterie);
  }, [ms]);
  return pret;
}

// Marches de data/prepared/, relus quand un telechargement se termine.
export function useMarches() {
  const { taches } = useDonnees();
  const cle = taches.filter(t => t.type === 'donnees').map(t => `${t.id}:${t.etat}`).join('|');
  const [marches, setMarches] = useState(null);
  useEffect(() => {
    let vivant = true;
    lire('/api/marches')
      .then(m => vivant && setMarches(m))
      .catch(() => vivant && setMarches([]));
    return () => {
      vivant = false;
    };
  }, [cle]);
  return marches;
}

// Configuration d'un run (config.toml), ou celle du bot si nom est undefined ; rien si nom est null. Un run
// ecrit sa configuration une fois, a sa creation : elle se lit sans risque pendant qu'il tourne.
const configs = new Map();
export function useConfig(nom) {
  const cle = nom ?? '';
  const [config, setConfig] = useState(() => (nom === null ? null : configs.get(cle) ?? null));
  useEffect(() => {
    if (nom === null) return setConfig(null);
    if (configs.has(cle)) return setConfig(configs.get(cle));
    let vivant = true;
    lire(`/api/config${nom ? `?depuis=${enc(nom)}` : ''}`)
      .then(c => {
        const valeurs = { ...c, valeurs: Object.fromEntries(c.champs.map(x => [x.cle, x.valeur])) };
        configs.set(cle, valeurs);
        if (vivant) setConfig(valeurs);
      })
      .catch(() => {});
    return () => {
      vivant = false;
    };
  }, [cle, nom]);
  return config;
}

// Detail d'un run (manifeste, configuration, Pantheon, rejeux), relu quand le run change d'etat : a l'arret,
// son Pantheon devient lisible.
export function useDetail(nom) {
  const { runs } = useDonnees();
  const r = runs.find(x => x.nom === nom);
  const cle = r ? [r.actif, r.point_de_sauvegarde, r.pantheon_rejoue, r.benchmark, r.rapport].join('|') : '';
  const [etat, setEtat] = useState({ detail: null, erreur: null });
  useEffect(() => {
    if (!nom) return;
    let vivant = true;
    lire(`/api/runs/${enc(nom)}`)
      .then(d => vivant && setEtat({ detail: d, erreur: null }))
      .catch(e => vivant && setEtat(p => ({ ...p, erreur: e.message })));
    return () => {
      vivant = false;
    };
  }, [nom, cle]);
  return etat;
}
