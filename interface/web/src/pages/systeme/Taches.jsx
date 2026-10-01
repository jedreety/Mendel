// Taches : tout ce que l'interface a lance, du plus recent au plus ancien. Un clic montre sa sortie.
import { useState } from 'react';
import { enc, envoyer } from '../../api.js';
import { useDonnees, useMaintenant } from '../../donnees.jsx';
import { duree, ilya, quand } from '../../format.js';
import { Carte, Copier, Message, Vide } from '../../composants/Base.jsx';
import Arret from '../../composants/Arret.jsx';
import Journal from '../../composants/Journal.jsx';
import StatusMark from '../../reactbits/StatusMark/StatusMark.jsx';
import FuseButton from '../../reactbits/FuseButton/FuseButton.jsx';
import { STATUTS, raconter } from '../../taches.js';

function Tuer({ tache }) {
  const { rafraichir } = useDonnees();
  const [erreur, setErreur] = useState(null);
  const tuer = async () => {
    try {
      await envoyer(`/api/taches/${enc(tache.id)}/arreter`, { mode: 'tuer' });
      rafraichir();
    } catch (e) {
      setErreur(e.message);
    }
  };
  return (
    <div className="grille" style={{ gap: 6 }}>
      <FuseButton label="Arrêter de force" undoLabel="Annuler" icon="croix" size="sm" color="#b02e2e" background="#fbeaea" undoWindow={4000} onCommit={tuer} />
      <span className="discret">Dernier recours : le dernier point de sauvegarde reste intact, mais le Panthéon n’est pas rejoué.</span>
      {erreur && <Message genre="critique">{erreur}</Message>}
    </div>
  );
}

export default function Taches() {
  const { taches, runs, tache } = useDonnees();
  const maintenant = useMaintenant(10000);
  const [ouverte, setOuverte] = useState(tache?.id ?? null);
  if (!taches.length) {
    return (
      <Carte>
        <Vide titre="Aucune tâche lancée">Chaque entraînement, benchmark, vérification ou téléchargement lancé d’ici apparaît ici, avec sa sortie.</Vide>
      </Carte>
    );
  }
  return (
    <Carte>
      <ul className="activite">
        {taches.map(t => {
          const { titre, issue } = raconter(t, runs, !t.run || taches.find(x => x.run === t.run) === t);
          const fin = t.fin_s ?? maintenant;
          const debut = Date.parse(t.debut) / 1000;
          return (
            <li key={t.id} style={{ gridTemplateColumns: '24px minmax(0, 1fr) auto', cursor: 'pointer' }} onClick={() => setOuverte(o => (o === t.id ? null : t.id))}>
              <StatusMark status={STATUTS[t.etat] ?? 'pending'} size={20} />
              <div className="activite-texte">
                <strong>{titre}</strong>
                <span>
                  {issue} · lancé le {quand(t.debut)} · {duree(fin - debut)}
                </span>
                {ouverte === t.id && (
                  <div className="grille" style={{ gap: 12, marginTop: 12, cursor: 'default' }} onClick={e => e.stopPropagation()}>
                    <div className="ligne">
                      <code className="mono" style={{ overflowWrap: 'anywhere' }}>
                        {t.commande}
                      </code>
                      <Copier texte={t.commande} />
                    </div>
                    {['en cours', 'arret demande'].includes(t.etat) && (
                      <div className="ligne" style={{ alignItems: 'flex-start', gap: 20 }}>
                        <Arret tache={t} />
                        <Tuer tache={t} />
                      </div>
                    )}
                    <Journal tacheId={t.id} hauteur={320} />
                  </div>
                )}
              </div>
              <span className="discret">{ilya(t.fin ?? t.debut, maintenant)}</span>
            </li>
          );
        })}
      </ul>
    </Carte>
  );
}
