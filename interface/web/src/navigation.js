// Plan du site : quatre sections dans le panneau lateral (Accueil, Entrainement, Bots, Systeme).
// L'adresse est dans le fragment : #/bots/<run>/<vue>, #/systeme/<page>, #/entrainement/<page>?bot=...

export const VUES_BOT = [
  { cle: 'resume', libelle: 'Résumé', icone: 'bot' },
  { cle: 'evolution', libelle: 'Évolution', icone: 'graphique' },
  { cle: 'benchmark', libelle: 'Benchmark', icone: 'cible' },
  { cle: 'details', libelle: 'Détails', icone: 'liste' }
];

export const PAGES_SYSTEME = [
  { cle: 'poste', libelle: 'Poste', icone: 'puce', description: 'GPU, processeur et mémoire en direct.' },
  { cle: 'taches', libelle: 'Tâches', icone: 'liste', description: 'Tout ce qui a été lancé, et sa sortie.' },
  { cle: 'donnees', libelle: 'Données', icone: 'donnees', description: 'Les marchés disponibles, et en ajouter un.' },
  { cle: 'diagnostic', libelle: 'Diagnostic', icone: 'pouls', description: 'Ce qu’il faut pour entraîner, vérifié.' },
  { cle: 'reglages', libelle: 'Réglages', icone: 'reglages', description: 'Effets visuels et notifications.' },
  { cle: 'lexique', libelle: 'Lexique', icone: 'livre', description: 'Chaque mot du bot, en une phrase ou deux.' }
];

// Adresse -> section et page. Les adresses de l'ancienne interface menent a la page la plus proche.
export function resoudre(parties) {
  const [s, a, b] = parties;
  if (s === 'run' && a) return { redirection: ['bots', a] };
  if (s === 'runs') return { redirection: ['bots'] };
  if (s === 'entrainement') return { section: 'entrainement', page: ['nouveau', 'continuer'].includes(a) ? a : null };
  if (s === 'bots') return a ? { section: 'bots', bot: a, vue: VUES_BOT.some(v => v.cle === b) ? b : 'resume' } : { section: 'bots' };
  if (s === 'systeme') return { section: 'systeme', page: PAGES_SYSTEME.some(p => p.cle === a) ? a : 'poste' };
  return { section: 'accueil' };
}
