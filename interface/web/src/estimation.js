// Estimation des durees d'entrainement d'apres les runs deja faits : secondes par bot evalue.
// Les runs sans empreinte de noyaux datent du simulateur en operations PyTorch, dix fois plus lent : faute de
// run recent, la reference est une mesure du noyau sur une RTX 3050 Ti (10 000 bots en 1,5 a 2 s).
const REFERENCE = { parBot: 1.75 / 10000, source: null };

export function vitesse(runs) {
  const recents = runs.filter(r => r.duree_moyenne_s && r.population && r.noyaux).sort((a, b) => b.nom.localeCompare(a.nom));
  const r = recents[0];
  return r ? { parBot: r.duree_moyenne_s / r.population, source: r } : REFERENCE;
}

// population : bots par generation ; generations : nombre prevu, ou null si l'arret n'est pas fixe.
export function estimer(runs, population, generations) {
  const v = vitesse(runs);
  const parGeneration = v.parBot * population;
  return {
    parGeneration,
    demarrage: 15 + parGeneration, // chargement, tables, noyaux, puis la population de reference
    total: generations ? 15 + parGeneration * (generations + 1) : null,
    source: v.source
  };
}
