// Sortie d'une tache, comme dans son terminal : filtre, recherche, suivi de la fin, copie et telechargement.
// Les lignes de generation, les avertissements et les erreurs ressortent.
import { useEffect, useMemo, useRef, useState } from 'react';
import { enc } from '../api.js';
import { useJournal } from '../donnees.jsx';
import { Copier, Icone, Segments } from './Base.jsx';

const LIGNES_MAX = 3000;
const ERREUR = /Traceback|Error|ECHEC|NON CONFORME|non conforme|refus/;
const ALERTE = /Attention|Arret|arret|stagne/;

function classe(ligne) {
  if (ERREUR.test(ligne)) return 'j-erreur';
  if (/^gen\s+\d/.test(ligne)) return 'j-gen';
  if (ALERTE.test(ligne)) return 'j-alerte';
  if (/^\s*ok\s|Tout est conforme|conforme$|Pantheon :/.test(ligne)) return 'j-ok';
  return undefined;
}

const FILTRES = {
  tout: () => true,
  generations: l => /^gen\s+\d/.test(l),
  alertes: l => ERREUR.test(l) || ALERTE.test(l) || /^\s+File |^\w+Error/.test(l)
};

export default function Journal({ tacheId, hauteur = 340, outils = true }) {
  const { texte, charge } = useJournal(tacheId);
  const [filtre, setFiltre] = useState('tout');
  const [recherche, setRecherche] = useState('');
  const [suivre, setSuivre] = useState(true);
  const boite = useRef(null);

  const toutes = useMemo(() => {
    const l = texte.replace(/\r\n/g, '\n').split('\n');
    if (l[l.length - 1] === '') l.pop();
    return l;
  }, [texte]);
  const lignes = useMemo(() => {
    const r = recherche.trim().toLowerCase();
    return toutes.filter(l => FILTRES[filtre](l) && (!r || l.toLowerCase().includes(r))).slice(-LIGNES_MAX);
  }, [toutes, filtre, recherche]);

  useEffect(() => {
    if (suivre && boite.current) boite.current.scrollTop = boite.current.scrollHeight;
  }, [lignes, suivre]);

  if (!tacheId) {
    return (
      <pre className="journal" style={{ height: hauteur }}>
        Aucune tâche lancée depuis l’interface.
      </pre>
    );
  }
  return (
    <div className="journal-cadre">
      {outils && (
        <div className="journal-outils">
          <Segments
            taille="sm"
            etiquette="Lignes montrées"
            actif={filtre}
            onChange={setFiltre}
            elements={[
              { cle: 'tout', libelle: 'Tout' },
              { cle: 'generations', libelle: 'Générations' },
              { cle: 'alertes', libelle: 'Alertes et erreurs' }
            ]}
          />
          <input className="saisie journal-recherche" placeholder="Chercher dans la sortie" value={recherche} onChange={e => setRecherche(e.target.value)} aria-label="Chercher dans la sortie" />
          <label className="interrupteur">
            <input type="checkbox" checked={suivre} onChange={e => setSuivre(e.target.checked)} />
            <span className="piste" />
            <span className="second">Suivre la fin</span>
          </label>
          <span className="pousse discret">
            {lignes.length} / {toutes.length} lignes
          </span>
          <Copier texte={texte} />
          <a className="bouton petit" href={`/api/taches/${enc(tacheId)}/journal/brut`} download title="Toute la sortie, dans un fichier">
            <Icone nom="telecharger" />
            Télécharger
          </a>
        </div>
      )}
      <pre
        className="journal"
        ref={boite}
        style={{ height: hauteur }}
        onScroll={e => {
          const el = e.currentTarget;
          const enBas = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
          if (enBas !== suivre) setSuivre(enBas);
        }}
      >
        {!charge && 'Lecture…'}
        {charge && toutes.length === 0 && 'Pas encore de sortie : le bot charge les données et compile ses noyaux.'}
        {charge && toutes.length > 0 && lignes.length === 0 && 'Aucune ligne ne correspond.'}
        {lignes.map((l, i) => (
          <div key={i} className={classe(l)}>
            {l || ' '}
          </div>
        ))}
      </pre>
    </div>
  );
}
