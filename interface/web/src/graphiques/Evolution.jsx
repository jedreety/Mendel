// Graphiques de generations.jsonl : notes, criteres de la note, argent des bots, validation des parents,
// amplitudes de mutation, durees. Un changement de lot de fenetres est marque d'un filet vertical ; la reprise
// d'un run aussi.
import { useMemo } from 'react';
import Courbes, { avecAlpha } from './Courbes.jsx';
import Graphique, { tableauDe } from './Graphique.jsx';
import { Vide } from '../composants/Base.jsx';
import { GROUPES, NOMS_GROUPES, NOMS_PHASES, argent, decimal, duree, note, pct } from '../format.js';

const generation = v => `génération ${Math.round(v)}`;
const precision = v => (v == null ? '–' : Number(v).toPrecision(3).replace('.', ','));
const graduationLog = v => String(Number(Number(v).toPrecision(2))).replace('.', ',');

export function marqueursLots(lignes) {
  const marqueurs = [];
  let avant = null;
  for (const l of lignes) {
    const n = l.lot?.numero;
    if (avant !== null && n !== avant) marqueurs.push({ x: l.generation, libelle: `nouvelles périodes` });
    avant = n;
  }
  return marqueurs;
}

function Attente() {
  return <Vide titre="Pas encore de génération">La première arrive quand le bot a évalué toute sa population une fois.</Vide>;
}

// Une note absolue (croissance du capital, pas de rangs) : les bots entraines depuis le 27 septembre 2026. Les
// anciens gardent leur note par rangs, de 0 a 1.
const absolue = lignes => lignes.some(l => l.note_confirmee_max != null);

// Les trois notes qui comptent : la meilleure de validation (celle qui choisit le champion), la meilleure
// d'entrainement, confirmee sur les periodes qui viennent de sortir du lot, et la mediane d'entrainement.
export function GraphNotes({ lignes, groupe, hauteur = 320, depart, titre = 'Les notes, génération après génération', actions }) {
  const nouvelle = absolue(lignes);
  const { x, series } = useMemo(
    () => ({
      x: lignes.map(l => l.generation),
      series: [
        { nom: 'Meilleure note de validation', couleur: 'var(--s1)', type: 'marches', largeur: 2.5, valeurs: lignes.map(l => l.meilleure_note_pantheon) },
        nouvelle
          ? { nom: 'Meilleure note confirmée', couleur: 'var(--s2)', valeurs: lignes.map(l => l.note_confirmee_max ?? null) }
          : { nom: 'Meilleure note d’entraînement', couleur: 'var(--s2)', valeurs: lignes.map(l => l.note_entrainement_max) },
        { nom: 'Note d’entraînement médiane', couleur: 'var(--s3)', valeurs: lignes.map(l => l.note_entrainement_mediane) }
      ]
    }),
    [lignes, nouvelle]
  );
  const marqueurs = useMemo(() => [...marqueursLots(lignes), ...(depart ? [{ x: depart - 0.5, libelle: 'reprise', couleur: '#8e8e96' }] : [])], [lignes, depart]);
  return (
    <Graphique
      titre={titre}
      sousTitre={
        nouvelle
          ? 'À peu près le gain par période de 90 jours, net de la pénalité de chute : 0,05 vaut +5 %. Un bot qui ne trade pas a −0,10. La note confirmée porte sur le lot et les périodes qui viennent d’en sortir ; la validation, sur une année que le bot n’apprend pas, décide du champion et monte par paliers, à chaque record.'
          : 'De 0 à 1, 1 pour le meilleur. La validation, sur une année que le bot n’apprend pas, décide du champion : elle monte par paliers, à chaque record.'
      }
      legende={series.map(s => ({ nom: s.nom, couleur: s.couleur }))}
      tableau={() => tableauDe(x, series, 'Génération', null, note)}
      actions={actions}
    >
      {lignes.length ? <Courbes x={x} series={series} hauteur={hauteur} formatY={note} formatAxeY={v => decimal(v, 2)} formatX={generation} marqueurs={marqueurs} groupe={groupe} yMin={nouvelle ? undefined : 0} /> : <Attente />}
    </Graphique>
  );
}

// Dans l'ordre de evolution/fitness.py, COMPOSANTES : les parts de la note absolue, leur somme est la note.
const PARTS = [
  ['croissance', 'Croissance du capital'],
  ['chute', 'Pénalité de chute'],
  ['preuve', 'Réduction faute de preuve'],
  ['activite', 'Pénalité d’inactivité']
];

// Les six composantes de l'ancienne note par rangs.
const CRITERES = [
  ['rendement', 'Rendement'],
  ['t', 't de l’espérance'],
  ['drawdown', 'Drawdown'],
  ['surperformance', 'Surperformance'],
  ['reussite', 'Taux de réussite'],
  ['trades', 'Nombre de trades']
];

function Absent() {
  return <Vide titre="Pas encore ce détail">Les générations écrites avant que le bot le note ne l’ont pas : il apparaît aux suivantes.</Vide>;
}

// La note du meilleur bot de chaque generation, part par part : la croissance, et ce que lui retirent la chute, le
// manque de preuve et l'inactivite. Leur somme est la note confirmee du meilleur bot.
function GraphParts({ lignes, groupe, hauteur, depart, actions }) {
  const { x, series } = useMemo(
    () => ({
      x: lignes.map(l => l.generation),
      series: [
        ...PARTS.map(([cle, nom], i) => ({ nom, couleur: `var(--s${i + 1})`, valeurs: lignes.map(l => l.criteres?.[cle] ?? null) })),
        { nom: 'Note du meilleur bot', couleur: 'var(--texte)', largeur: 1.5, valeurs: lignes.map(l => l.note_confirmee_max ?? null) }
      ]
    }),
    [lignes]
  );
  const marqueurs = useMemo(() => [...marqueursLots(lignes), ...(depart ? [{ x: depart - 0.5, libelle: 'reprise', couleur: '#8e8e96' }] : [])], [lignes, depart]);
  return (
    <Graphique
      titre="Les parts de la note"
      sousTitre="La note du meilleur bot de chaque génération : ce que son capital a gagné, moins ce que lui retirent sa pire chute, le manque de trades pour prouver son gain et l’inactivité. Leur somme est sa note."
      legende={series.map(s => ({ nom: s.nom, couleur: s.couleur }))}
      tableau={() => tableauDe(x, series, 'Génération', null, note)}
      actions={actions}
    >
      <Courbes x={x} series={series} hauteur={hauteur} formatY={note} formatAxeY={v => decimal(v, 2)} formatX={generation} marqueurs={marqueurs} groupe={groupe} />
    </Graphique>
  );
}

// Les criteres de la note : ses parts pour une note absolue, ses composantes pour une ancienne note par rangs.
export function GraphCriteres({ lignes, poids, groupe, hauteur = 320, depart, actions }) {
  if (lignes.length && absolue(lignes)) return <GraphParts lignes={lignes} groupe={groupe} hauteur={hauteur} depart={depart} actions={actions} />;
  return <GraphComposantes lignes={lignes} poids={poids} groupe={groupe} hauteur={hauteur} depart={depart} actions={actions} />;
}

// L'ancienne note par rangs, empilee critere par critere. Chaque couche vaut le poids du critere fois son rang parmi
// les bots de la generation, agrege sur les fenetres comme la note elle-meme : empilees, elles font la note.
function GraphComposantes({ lignes, poids, groupe, hauteur, depart, actions }) {
  const { x, series, legende } = useMemo(() => {
    let cumul = lignes.map(() => 0);
    const couches = CRITERES.map(([cle, nom], i) => {
      const brut = lignes.map(l => l.criteres?.[cle] ?? null);
      cumul = cumul.map((c, j) => (c == null || brut[j] == null ? null : c + brut[j]));
      const p = poids?.[cle] != null ? Number(poids[cle]) : null;
      return {
        nom,
        couleur: `var(--s${i + 1})`,
        remplissage: `var(--s${i + 1})`,
        trait: '#ffffff',
        sur: i ? i - 1 : undefined,
        valeurs: cumul,
        infobulle: brut,
        format: p == null ? note : v => `${note(v)} sur ${decimal(p, 2)}`,
        poids: p
      };
    });
    return {
      x: lignes.map(l => l.generation),
      series: [...couches, { nom: 'Note du meilleur bot', couleur: 'var(--texte)', largeur: 1.5, valeurs: lignes.map(l => l.note_entrainement_max) }],
      legende: [...couches.map(c => ({ nom: c.poids == null ? c.nom : `${c.nom} · ${pct(c.poids, 0)}`, couleur: c.couleur, forme: 'rect' })), { nom: 'Note du meilleur bot', couleur: 'var(--texte)' }]
    };
  }, [lignes, poids]);
  const marqueurs = useMemo(() => [...marqueursLots(lignes), ...(depart ? [{ x: depart - 0.5, libelle: 'reprise', couleur: '#8e8e96' }] : [])], [lignes, depart]);
  const tableau = () => tableauDe(x, series.map(s => ({ ...s, valeurs: s.infobulle ?? s.valeurs })), 'Génération', null, note);
  return (
    <Graphique
      titre="Les critères de la note"
      sousTitre="La note du meilleur bot de chaque génération : chaque couche est le poids d’un critère fois son rang parmi les bots."
      legende={legende}
      tableau={tableau}
      actions={actions}
    >
      {!lignes.length ? <Attente /> : !lignes.some(l => l.criteres) ? <Absent /> : <Courbes x={x} series={series} hauteur={hauteur} formatY={note} formatAxeY={v => decimal(v, 2)} formatX={generation} marqueurs={marqueurs} groupe={groupe} yMin={0} />}
    </Graphique>
  );
}

// L'argent de chaque bot en fin de periode, en moyenne sur les periodes du lot : le meilleur de la generation,
// le bot median, et la bande ou finissent 8 bots sur 10, face au capital de depart.
export function GraphArgent({ lignes, capital, cotation, groupe, hauteur = 320, depart, actions }) {
  const { x, series } = useMemo(() => {
    const valeur = cle => lignes.map(l => l.capital_final?.[cle] ?? null);
    const bord = avecAlpha('var(--s1)', 0.35);
    return {
      x: lignes.map(l => l.generation),
      series: [
        { nom: 'Seuil des 10 % du bas', couleur: 'var(--s1)', trait: bord, largeur: 1, valeurs: valeur('p10') },
        { nom: 'Seuil des 10 % du haut', couleur: 'var(--s1)', trait: bord, largeur: 1, remplissage: avecAlpha('var(--s1)', 0.12), sur: 0, valeurs: valeur('p90') },
        { nom: 'Bot médian', couleur: 'var(--s1)', valeurs: valeur('mediane') },
        { nom: 'Meilleur bot de la génération', couleur: 'var(--s2)', valeurs: valeur('meilleur') }
      ]
    };
  }, [lignes]);
  const marqueurs = useMemo(() => [...marqueursLots(lignes), ...(depart ? [{ x: depart - 0.5, libelle: 'reprise', couleur: '#8e8e96' }] : [])], [lignes, depart]);
  const depot = capital == null ? null : Number(capital);
  const format = v => argent(v, cotation, 2);
  return (
    <Graphique
      titre="L’argent des bots"
      sousTitre={`Ce qu’il reste à chaque bot en fin de période, en moyenne sur les périodes étudiées. Tous partent de ${depot == null ? 'la même somme' : argent(depot, cotation)}.`}
      legende={[
        { nom: '8 bots sur 10 finissent dans cette bande', couleur: avecAlpha('var(--s1)', 0.3), forme: 'rect' },
        { nom: 'Bot médian', couleur: 'var(--s1)' },
        { nom: 'Meilleur bot de la génération', couleur: 'var(--s2)' }
      ]}
      tableau={() => tableauDe(x, series, 'Génération', null, format)}
      actions={actions}
    >
      {!lignes.length ? (
        <Attente />
      ) : !lignes.some(l => l.capital_final) ? (
        <Absent />
      ) : (
        <Courbes x={x} series={series} hauteur={hauteur} formatY={format} formatAxeY={v => argent(v)} formatX={generation} marqueurs={marqueurs} references={depot == null ? [] : [{ valeur: depot, libelle: 'départ' }]} groupe={groupe} yMin={depot ?? undefined} yMax={depot ?? undefined} />
      )}
    </Graphique>
  );
}

// Les parents de chaque generation, legerement decales autour de leur generation.
function etaler(lignes, valeur) {
  const x = [];
  const valeurs = [];
  const meilleure = [];
  for (const l of lignes) {
    const n = l.parents.length;
    l.parents.forEach((p, k) => {
      x.push(l.generation + (k - (n - 1) / 2) * 0.12);
      valeurs.push(valeur(p));
      meilleure.push(l.meilleure_note_pantheon);
    });
  }
  return { x, valeurs, meilleure };
}

export function GraphValidation({ lignes, groupe, hauteur = 240 }) {
  const { x, series } = useMemo(() => {
    const { x, valeurs, meilleure } = etaler(lignes, p => p.note_validation);
    return {
      x,
      series: [
        { nom: 'Note de validation d’un parent', type: 'points', couleur: 'var(--s1)', valeurs },
        { nom: 'Meilleure note de validation', type: 'marches', couleur: 'var(--s2)', valeurs: meilleure }
      ]
    };
  }, [lignes]);
  return (
    <Graphique
      titre="Les candidats de chaque génération"
      sousTitre="Les parents de chaque génération, passés en validation. Un point au-dessus de la marche est un record."
      legende={series.map(s => ({ nom: s.nom, couleur: s.couleur, forme: s.type }))}
      tableau={() => tableauDe(x.map(Math.round), series, 'Génération', null, note)}
    >
      {lignes.length ? <Courbes x={x} series={series} hauteur={hauteur} formatY={note} formatAxeY={v => decimal(v, 2)} formatX={generation} groupe={groupe} /> : <Attente />}
    </Graphique>
  );
}

export function GraphSigma({ lignes, groupe, hauteur = 220 }) {
  const { x, series } = useMemo(
    () => ({
      x: lignes.map(l => l.generation),
      series: GROUPES.map((g, i) => ({ nom: NOMS_GROUPES[g], couleur: `var(--s${i + 1})`, valeurs: lignes.map(l => l.sigma_moyen?.[g] ?? null) }))
    }),
    [lignes]
  );
  return (
    <Graphique titre="Force des mutations" sousTitre="L’amplitude de chaque groupe de gènes, en moyenne sur les enfants (échelle logarithmique). Elle s’ajuste d’elle-même ; chaque enfant, puis chacun de ses gènes, tire en plus sa propre ampleur autour d’elle." legende={series.map(s => ({ nom: s.nom, couleur: s.couleur }))} tableau={() => tableauDe(x, series, 'Génération', null, precision)}>
      {lignes.length ? <Courbes x={x} series={series} hauteur={hauteur} log formatY={precision} formatAxeY={graduationLog} formatX={generation} groupe={groupe} /> : <Attente />}
    </Graphique>
  );
}

export function GraphDurees({ lignes, groupe, hauteur = 220 }) {
  const { x, series } = useMemo(() => {
    const phases = [...new Set(lignes.flatMap(l => Object.keys(l.durees_s ?? {})))];
    return {
      x: lignes.map(l => l.generation),
      series: [
        { nom: 'Génération entière', couleur: 'var(--s1)', valeurs: lignes.map(l => l.duree_s) },
        ...phases.slice(0, 4).map((p, i) => ({ nom: NOMS_PHASES[p] ?? p, couleur: `var(--s${i + 2})`, valeurs: lignes.map(l => l.durees_s?.[p] ?? null) }))
      ]
    };
  }, [lignes]);
  return (
    <Graphique titre="Durée des générations" sousTitre="En secondes, la génération entière et chacune de ses étapes." legende={series.map(s => ({ nom: s.nom, couleur: s.couleur }))} tableau={() => tableauDe(x, series, 'Génération', null, duree)}>
      {lignes.length ? <Courbes x={x} series={series} hauteur={hauteur} formatY={duree} formatAxeY={v => decimal(v, 1)} formatX={generation} groupe={groupe} yMin={0} /> : <Attente />}
    </Graphique>
  );
}
