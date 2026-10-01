// Mise en forme francaise. Les instants du bot sont en UTC : ils sont affiches en UTC. Entre un nombre et son
// unite, une espace insecable (ESP) : la ligne ne se coupe pas entre les deux.

const formats = new Map();
function nf(min, max) {
  const cle = `${min}-${max}`;
  if (!formats.has(cle)) formats.set(cle, new Intl.NumberFormat('fr-FR', { minimumFractionDigits: min, maximumFractionDigits: max }));
  return formats.get(cle);
}

const vide = v => v === null || v === undefined || Number.isNaN(v);
const ESP = '\u00a0';

export const note = v => (vide(v) ? '–' : nf(4, 4).format(v));
export const nombre = (v, d = 0) => (vide(v) ? '–' : nf(d, d).format(v));
export const decimal = (v, d = 2) => (vide(v) ? '–' : nf(0, d).format(v));
export const pct = (v, d = 1) => (vide(v) ? '–' : `${nf(d, d).format(v * 100)}${ESP}%`);
export const signe = (v, d = 2) => (vide(v) ? '–' : `${v > 0 ? '+' : ''}${nf(d, d).format(v)}`);
export const pctSigne = (v, d = 2) => (vide(v) ? '–' : `${v > 0 ? '+' : ''}${nf(d, d).format(v * 100)}${ESP}%`);

export function compact(v) {
  if (vide(v)) return '–';
  const a = Math.abs(v);
  if (a >= 1e9) return `${nf(0, 1).format(v / 1e9)}${ESP}G`;
  if (a >= 1e6) return `${nf(0, 1).format(v / 1e6)}${ESP}M`;
  if (a >= 1e4) return `${nf(0, 1).format(v / 1e3)}${ESP}k`;
  return nf(0, 0).format(v);
}

export function octets(v) {
  if (vide(v)) return '–';
  if (v >= 1024 ** 3) return `${nf(1, 1).format(v / 1024 ** 3)}${ESP}Go`;
  if (v >= 1024 ** 2) return `${nf(0, 0).format(v / 1024 ** 2)}${ESP}Mo`;
  return `${nf(0, 0).format(v / 1024)}${ESP}Ko`;
}

export function mo(v) {
  if (vide(v)) return '–';
  return v >= 1024 ? `${nf(2, 2).format(v / 1024)}${ESP}Go` : `${nf(0, 0).format(v)}${ESP}Mo`;
}

export function duree(s) {
  if (vide(s)) return '–';
  if (s < 10) return `${nf(1, 1).format(s)}${ESP}s`;
  if (s < 60) return `${Math.round(s)}${ESP}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}${ESP}min ${String(Math.round(s % 60)).padStart(2, '0')}${ESP}s`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}${ESP}h ${String(m % 60).padStart(2, '0')}${ESP}min`;
  return `${Math.floor(h / 24)}${ESP}j ${h % 24}${ESP}h`;
}

const dateHeure = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const dateSeule = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' });
const heureSeule = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit' });
const dateCourte = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', day: 'numeric', month: 'short' });
const dateCourteHeure = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

const enDate = v => (v instanceof Date ? v : typeof v === 'number' ? new Date(v * 1000) : new Date(String(v).replace(' ', 'T')));

export const quand = v => (vide(v) || v === '' ? '–' : `${dateHeure.format(enDate(v))} UTC`);
export const jour = v => (vide(v) || v === '' ? '–' : dateSeule.format(enDate(v)));
export const heure = v => (vide(v) || v === '' ? '–' : heureSeule.format(enDate(v)));
export const jourCourt = v => (vide(v) || v === '' ? '–' : dateCourte.format(enDate(v)));
export const jourHeure = v => (vide(v) || v === '' ? '–' : dateCourteHeure.format(enDate(v)));

// « il y a 3 min » : instant en texte ISO ou en secondes, maintenant en secondes (horloge du serveur).
export function ilya(instant, maintenant) {
  if (vide(instant) || instant === '') return '–';
  const t = typeof instant === 'number' ? instant : enDate(instant).getTime() / 1000;
  const s = Math.max(0, maintenant - t);
  if (s < 45) return 'à l’instant';
  if (s < 3600) return `il y a ${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  const j = Math.floor(s / 86400);
  return `il y a ${j} jour${j > 1 ? 's' : ''}`;
}

// Montant dans la monnaie de cotation du marche : « 1 000 USDT ».
export const argent = (v, cotation = '', d = 0) => (vide(v) ? '–' : `${nf(d, d).format(Number(v))}${cotation ? `${ESP}${cotation}` : ''}`);

// Date d'un run a partir de son nom : 20260926T103617Z-evolution
export function dateRun(nom) {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(nom || '');
  return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6])) : null;
}

export const TYPES_TACHES = {
  nouveau: 'Entraînement',
  reprendre: 'Entraînement',
  'a-blanc': 'Run à blanc',
  hasard: 'Recherche aléatoire',
  verifier: 'Vérification des noyaux',
  benchmark: 'Benchmark',
  donnees: 'Téléchargement'
};
export const ICONES_TACHES = { nouveau: 'eclair', reprendre: 'eclair', 'a-blanc': 'balance', hasard: 'balance', verifier: 'pouls', benchmark: 'cible', donnees: 'telecharger' };
export const GROUPES = ['modules', 'reseau', 'decision', 'adaptation'];
export const NOMS_GROUPES = { modules: 'Modules', reseau: 'Réseau', decision: 'Décision', adaptation: 'Adaptation' };
export const NOMS_PHASES = { evaluation: 'Évaluation', selection_et_validation: 'Sélection et validation', admission: 'Admission', rejeu: 'Rejeu' };
