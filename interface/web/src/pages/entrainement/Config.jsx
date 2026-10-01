// Parametres avances d'un nouvel entrainement : chaque parametre de evolution/config.toml, groupe par section
// du fichier, avec sa description et ce qui differe de la configuration du bot. Le texte du fichier n'est
// modifie que sur la valeur du parametre touche : commentaires et ordre restent.
import { useMemo } from 'react';
import { PARAMETRES } from '../../glossaire.js';

const MOTIFS = { entier: /^-?\d+$/, decimal: /^-?\d+(\.\d+)?$/, date: /^\d{4}-\d{2}-\d{2}$/ };

export const LIBELLES = {
  donnees: 'Fichier de données',
  debut_entrainement: 'Début de l’entraînement',
  debut_validation: 'Début de la validation',
  debut_test: 'Début du test',
  fenetres_par_lot: 'Fenêtres par lot',
  duree_fenetre_jours: 'Durée d’une fenêtre (jours)',
  prechauffage_jours: 'Préchauffage (jours)',
  renouvellement_lot: 'Durée de vie d’une période (générations)',
  capital_initial: 'Capital de départ',
  frais_entrainement: 'Frais à l’entraînement (min, max)',
  glissement_entrainement: 'Glissement à l’entraînement (min, max)',
  frais_reference: 'Frais en validation et en test',
  glissement_reference: 'Glissement en validation et en test',
  pas_de_prix: 'Pas de prix',
  pas_de_quantite: 'Pas de quantité',
  notionnel_minimum: 'Ordre minimum',
  taille_cachee: 'Neurones cachés',
  canaux_modules: 'Canaux des modules',
  duree_max_barres: 'Durée maximale d’un trade (heures)',
  adaptation_en_vie: 'Adaptation pendant la vie',
  population: 'Bots par génération',
  nb_parents: 'Parents',
  seuil_distinction: 'Seuil de distinction',
  candidats_examines: 'Candidats examinés',
  sigma_initial_reseau: 'Mutation initiale du réseau',
  sigma_initial_autres: 'Mutation initiale des autres gènes',
  amplitude_marge: 'Marge des amplitudes de mutation',
  mutation_enfant: 'Force de mutation d’un enfant (min, max)',
  mutation_gene: 'Ampleur de mutation d’un gène (min, max)',
  proba_categoriel: 'Probabilité de retirer un choix',
  graine_maitresse: 'Graine',
  penalite_chute: 'Pénalité de chute',
  trades_preuve: 'Trades de preuve par fenêtre',
  trades_minimum: 'Trades minimum par fenêtre',
  penalite_inactivite: 'Pénalité d’inactivité',
  seuil_ruine: 'Seuil de ruine',
  agregation: 'Agrégation des fenêtres',
  population_reference: 'Population de référence',
  memoire_gpu_max: 'Part de la mémoire GPU',
  stagnation_max: 'Arrêt sur stagnation (générations)',
  generations_max: 'Générations au plus',
  tolerance_rejeu: 'Tolérance du rejeu'
};

export function litteral(type, valeur) {
  if (type === 'booleen') return valeur ? 'true' : 'false';
  if (type === 'texte') return JSON.stringify(valeur);
  if (type === 'liste') return `[${valeur.join(', ')}]`;
  if (type === 'table') return `{ ${Object.entries(valeur).map(([k, v]) => `${k} = ${v}`).join(', ')} }`;
  return String(valeur);
}

export function valide(type, valeur) {
  if (type === 'liste') return valeur.every(v => MOTIFS.decimal.test(String(v)));
  if (type === 'table') return Object.values(valeur).every(v => MOTIFS.decimal.test(String(v)));
  return MOTIFS[type] ? MOTIFS[type].test(String(valeur)) : true;
}

export function egal(type, a, b) {
  if (a == null || b == null) return a === b;
  if (type === 'decimal' || type === 'entier') return Number(a) === Number(b);
  if (type === 'liste') return a.length === b.length && a.every((x, i) => Number(x) === Number(b[i]));
  if (type === 'table') return Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => Number(a[k]) === Number(b[k]));
  return String(a) === String(b);
}

// Remplace la valeur d'un champ dans sa ligne ; le reste du texte, commentaires compris, ne bouge pas.
export function appliquer(config, cle, valeur) {
  const champ = config.champs.find(c => c.cle === cle);
  if (!champ) return config;
  const lignes = config.texte.split('\n');
  const texte = litteral(champ.type, valeur);
  const ligne = lignes[champ.ligne];
  lignes[champ.ligne] = ligne.slice(0, champ.debut) + texte + ligne.slice(champ.fin);
  return { texte: lignes.join('\n'), champs: config.champs.map(c => (c === champ ? { ...c, valeur, fin: c.debut + texte.length } : c)) };
}

export const valeurDe = (config, cle) => config?.champs.find(c => c.cle === cle)?.valeur;

function Saisie({ champ, changer }) {
  const v = champ.valeur;
  if (champ.type === 'booleen') {
    return (
      <label className="interrupteur">
        <input type="checkbox" checked={!!v} onChange={e => changer(e.target.checked)} />
        <span className="piste" />
        <span className="second">{v ? 'oui' : 'non'}</span>
      </label>
    );
  }
  if (champ.type === 'liste') {
    return (
      <div className="ligne" style={{ flexWrap: 'nowrap' }}>
        {v.map((x, i) => (
          <input key={i} className={`saisie ${MOTIFS.decimal.test(String(x)) ? '' : 'invalide'}`} value={x} onChange={e => changer(v.map((y, j) => (j === i ? e.target.value : y)))} aria-label={`${champ.cle} ${i === 0 ? 'minimum' : 'maximum'}`} />
        ))}
      </div>
    );
  }
  if (champ.type === 'table') {
    return (
      <div className="champs" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 8 }}>
        {Object.entries(v).map(([k, x]) => (
          <label key={k} className="champ">
            <small>{k}</small>
            <input className={`saisie ${MOTIFS.decimal.test(String(x)) ? '' : 'invalide'}`} value={x} onChange={e => changer({ ...v, [k]: e.target.value })} />
          </label>
        ))}
      </div>
    );
  }
  return (
    <input
      className={`saisie ${valide(champ.type, v) ? '' : 'invalide'}`}
      type={champ.type === 'date' ? 'date' : 'text'}
      inputMode={champ.type === 'entier' || champ.type === 'decimal' ? 'decimal' : undefined}
      value={v}
      onChange={e => changer(champ.type === 'entier' && MOTIFS.entier.test(e.target.value) ? Number(e.target.value) : e.target.value)}
      aria-label={LIBELLES[champ.cle] ?? champ.cle}
    />
  );
}

export default function EditeurConfig({ config, setConfig, defaut, exclure = [] }) {
  const parCle = useMemo(() => Object.fromEntries((defaut ?? []).map(c => [c.cle, c])), [defaut]);
  const sections = useMemo(() => {
    const s = new Map();
    for (const c of config.champs) {
      if (exclure.includes(c.cle)) continue;
      if (!s.has(c.section)) s.set(c.section, []);
      s.get(c.section).push(c);
    }
    return [...s.entries()];
  }, [config.champs, exclure]);
  return (
    <>
      {sections.map(([section, champs]) => {
        const modifies = champs.filter(c => parCle[c.cle] && !egal(c.type, c.valeur, parCle[c.cle].valeur)).length;
        return (
          <div className="section-form" key={section ?? 'autres'}>
            <h3>
              {section ?? 'Autres paramètres'}
              {modifies > 0 && <span className="etiquette accent">{modifies} modifié{modifies > 1 ? 's' : ''}</span>}
            </h3>
            <div className="champs">
              {champs.map(c => {
                const origine = parCle[c.cle];
                const modifie = origine && !egal(c.type, c.valeur, origine.valeur);
                return (
                  <div className={`champ ${modifie ? 'champ-modifie' : ''}`} key={c.cle} style={c.type === 'table' ? { gridColumn: '1 / -1' } : undefined}>
                    <span className="champ-nom">
                      {LIBELLES[c.cle] ?? c.cle}
                      {modifie && (
                        <button type="button" className="lien pousse" style={{ fontSize: 12 }} onClick={() => setConfig(appliquer(config, c.cle, origine.valeur))} title={`Revenir à ${litteral(origine.type, origine.valeur)}`}>
                          rétablir
                        </button>
                      )}
                    </span>
                    <Saisie champ={c} changer={v => setConfig(appliquer(config, c.cle, v))} />
                    {PARAMETRES[c.cle] && <small>{PARAMETRES[c.cle]}</small>}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </>
  );
}
