// Exports de fichiers depuis le navigateur. Les nombres gardent le point decimal : ils restent lisibles par
// un programme ; la marque d'ordre des octets fait lire l'UTF-8 aux tableurs.

export function telecharger(nom, texte, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob(['﻿', texte], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function telechargerCSV(nom, colonnes, lignes) {
  const champ = v => {
    if (v == null) return '';
    const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  telecharger(nom, [colonnes, ...lignes].map(l => l.map(champ).join(',')).join('\n'), 'text/csv;charset=utf-8');
}

// Une ligne par generation, pour un tableur.
export function generationsCSV(run, lignes) {
  const phases = [...new Set(lignes.flatMap(l => Object.keys(l.durees_s ?? {})))];
  const groupes = [...new Set(lignes.flatMap(l => Object.keys(l.sigma_moyen ?? {})))];
  telechargerCSV(
    `${run}-generations.csv`,
    ['generation', 'date', 'duree_s', ...phases.map(p => `duree_${p}_s`), 'memoire_max_mo', 'bots_evalues', 'validations_uniques', 'lot', 'note_entrainement_max', 'note_entrainement_mediane', 'meilleure_note_pantheon', 'champion', 'parents', 'notes_validation_parents', ...groupes.map(g => `sigma_${g}`)],
    lignes.map(l => [
      l.generation,
      l.date,
      l.duree_s,
      ...phases.map(p => l.durees_s?.[p]),
      l.memoire_max_mo,
      l.bots_evalues,
      l.validations_uniques,
      l.lot?.numero,
      l.note_entrainement_max,
      l.note_entrainement_mediane,
      l.meilleure_note_pantheon,
      l.pantheon?.[0]?.id,
      l.parents.map(p => p.id).join(' '),
      l.parents.map(p => p.note_validation).join(' '),
      ...groupes.map(g => l.sigma_moyen?.[g])
    ])
  );
}
