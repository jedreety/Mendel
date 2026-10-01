// Les taches racontees simplement : une ligne pour dire ce qui a ete fait, sur quel bot, et comment ca a fini.
import { nomRun } from './bots.js';

export const ENTRAINEMENTS = ['nouveau', 'reprendre', 'a-blanc', 'hasard'];
export const STATUTS = {
  'en cours': 'running',
  'arret demande': 'running',
  terminee: 'done',
  arretee: 'done',
  interrompue: 'cancelled',
  echec: 'failed',
  tuee: 'failed'
};
const ISSUES = { terminee: 'terminé', arretee: 'arrêté proprement', interrompue: 'interrompu', echec: 'a échoué', tuee: 'arrêté de force' };

// Une tache racontee en une ligne : ce qui a ete fait, sur quel bot, et comment ca s'est fini. La generation
// atteinte n'est donnee que pour la derniere tache d'un run : les suivantes l'ont peut-etre prolonge.
export function raconter(t, runs, derniereDuRun = true) {
  const run = runs.find(r => r.nom === (t.source ?? t.run));
  const bot = run ? `« ${nomRun(run.source ? runs.find(r => r.nom === run.source) ?? run : run, runs)} »` : t.nom ? `« ${t.nom} »` : '';
  // La reprise d'un temoin reste un run a blanc ou une recherche aleatoire.
  const genre = t.type === 'reprendre' && run && run.mode !== 'reel' ? run.mode : t.type;
  const titres = {
    nouveau: `Création du bot ${bot}`,
    reprendre: `Entraînement de ${bot}`,
    'a-blanc': `Run à blanc de ${bot}`,
    hasard: `Recherche aléatoire pour ${bot}`,
    benchmark: `Benchmark de ${bot}`,
    verifier: 'Vérification des noyaux',
    donnees: `Téléchargement de ${t.symbole ?? 'données'}`
  };
  const cible = ENTRAINEMENTS.includes(t.type) && derniereDuRun ? runs.find(r => r.nom === t.run) : null;
  const jusqua = cible && !['en cours', 'arret demande'].includes(t.etat) ? `, à la génération ${cible.generation}` : '';
  return { titre: titres[genre] ?? t.type, issue: t.etat === 'en cours' ? 'en cours' : t.etat === 'arret demande' ? 'arrêt demandé' : `${ISSUES[t.etat] ?? t.etat}${jusqua}` };
}

