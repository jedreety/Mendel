// Le benchmark d'un bot : le champion passe une fois le bloc de test, sans rien
// apprendre, face au bot tire au hasard. Son etat, et ce qu'il y a a faire maintenant pour ce bot.
import { lien } from './route.js';

export function protocole(reel) {
  const benchmark = reel.rapport ? 'fait' : reel.benchmark ? 'interrompu' : !reel.actif && reel.champion ? 'pret' : 'bloque';
  return { benchmark, suite: suite(reel, benchmark) };
}

// Ce qu'il y a a faire maintenant pour ce bot, en une phrase et une action.
function suite(reel, benchmark) {
  const page = lien(['bots', reel.nom, 'benchmark']);
  if (reel.actif) return { texte: 'Il s’entraîne en ce moment.', action: 'Suivre en direct', href: '#/entrainement' };
  if (benchmark === 'pret') return { texte: 'Il est prêt pour le benchmark, qui ne s’ouvre qu’une fois.', action: 'Préparer le benchmark', href: page };
  if (benchmark === 'fait') return { texte: 'Son benchmark est fait : voyez ses trades sur des données jamais vues.', action: 'Voir le benchmark', href: page };
  if (benchmark === 'interrompu') return { texte: 'Son benchmark a été interrompu : le bloc de test est considéré comme ouvert.', action: 'Voir', href: page };
  return { texte: 'Il n’a pas encore de Panthéon.', action: 'Voir le bot', href: lien(['bots', reel.nom]) };
}
