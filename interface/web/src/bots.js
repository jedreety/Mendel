// Les bots, tels que l'interface les presente : un bot est un run reel, sur un seul marche ; son run a blanc et
// sa recherche aleatoire sont ses temoins. Ici : leur nom, leur marche, et leur suppression differee.
import { useSyncExternalStore } from 'react';
import { enc, envoyer } from './api.js';
import { dateRun, jourHeure } from './format.js';
import { notifier } from './composants/Notifications.jsx';

const COTATIONS = ['USDT', 'USDC', 'FDUSD', 'BUSD', 'TUSD', 'EUR', 'TRY', 'BRL', 'GBP', 'JPY', 'BTC', 'ETH', 'BNB'];

// BTCUSDT -> { base: 'BTC', cotation: 'USDT' }. Le symbole est lu dans le nom du fichier de donnees.
export function paire(symbole) {
  const s = symbole ?? '';
  const cotation = COTATIONS.find(c => s.endsWith(c) && s.length > c.length);
  return cotation ? { base: s.slice(0, -cotation.length), cotation } : { base: s, cotation: '' };
}

export function libellePaire(symbole) {
  const p = paire(symbole);
  return p.cotation ? `${p.base} / ${p.cotation}` : p.base || '–';
}

export const annee = iso => (iso ? Number(String(iso).slice(0, 4)) : null);

// Nom donne dans l'interface, sinon le marche et l'instant de creation.
export function nomBot(run) {
  if (!run) return '';
  if (run.nom_bot) return run.nom_bot;
  const d = dateRun(run.nom);
  return `${paire(run.symbole).base || 'Bot'} du ${d ? jourHeure(d) : run.nom}`;
}

// Nom de n'importe quel run : un temoin porte le nom de son bot.
export function nomRun(run, runs) {
  if (!run) return '';
  if (!run.source) return nomBot(run);
  const source = runs.find(r => r.nom === run.source);
  return `${source ? nomBot(source) : run.source} · ${run.mode === 'a-blanc' ? 'run à blanc' : 'recherche aléatoire'}`;
}

// Les bots, du plus recemment ecrit au plus ancien.
export function listeBots(runs) {
  return runs.filter(r => r.mode === 'reel').sort((a, b) => String(b.ecriture ?? b.nom).localeCompare(String(a.ecriture ?? a.nom)));
}

// Periode lisible d'un bot : « entraîné sur 2020 → 2023 ».
export function periode(run) {
  const a = annee(run?.debut_entrainement);
  const v = annee(run?.debut_validation);
  if (!a || !v) return '';
  return v - 1 > a ? `${a} → ${v - 1}` : `${a}`;
}

export async function renommer(run, nom) {
  await envoyer(`/api/bots/${enc(run)}/nom`, { nom });
}

// --- Suppressions en attente ---
// La ligne disparait tout de suite ; la corbeille n'est appelee qu'au bout du delai, sauf « Annuler ».

let enAttente = new Set();
const abonnes = new Set();
const publier = () => abonnes.forEach(f => f());
const retirer = run => {
  enAttente = new Set(enAttente);
  enAttente.delete(run);
  publier();
};

export function useSuppressions() {
  return useSyncExternalStore(
    f => {
      abonnes.add(f);
      return () => abonnes.delete(f);
    },
    () => enAttente
  );
}

export function supprimerBot(run, nom, delai = 6000) {
  enAttente = new Set(enAttente).add(run);
  publier();
  const executer = async () => {
    try {
      await envoyer(`/api/bots/${enc(run)}/supprimer`, {});
      notifier({ genre: 'bon', titre: `« ${nom} » est dans la corbeille`, texte: 'Il se restaure depuis la corbeille de Windows, avec ses témoins.' });
    } catch (e) {
      retirer(run); // la ligne revient
      notifier({ genre: 'critique', titre: 'Suppression impossible', texte: e.message, duree: 12000 });
    }
  };
  if (!delai) return executer();
  const minuterie = setTimeout(executer, delai);
  notifier({
    genre: 'alerte',
    titre: `« ${nom} » va être supprimé`,
    texte: 'Son dossier et ceux de ses témoins partent à la corbeille.',
    duree: delai,
    meche: true,
    action: {
      libelle: 'Annuler',
      faire: () => {
        clearTimeout(minuterie);
        retirer(run);
      }
    }
  });
}
