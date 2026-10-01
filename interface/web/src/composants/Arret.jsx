// Arret d'une tache, comme au clavier : un Ctrl+C finit la generation en cours, sauvegarde et rejoue le
// Pantheon ; un second interrompt sur-le-champ, le dernier point de sauvegarde restant intact. Chaque demande
// part au bout d'une meche de trois secondes, pendant laquelle « Annuler » la retient.
import { useState } from 'react';
import { enc, envoyer } from '../api.js';
import { useDonnees } from '../donnees.jsx';
import { Message } from './Base.jsx';
import FuseButton from '../reactbits/FuseButton/FuseButton.jsx';

export default function Arret({ tache }) {
  const { rafraichir } = useDonnees();
  const [erreur, setErreur] = useState(null);
  if (!tache) return null;
  const entrainement = ['nouveau', 'reprendre', 'a-blanc', 'hasard'].includes(tache.type);

  const arreter = async () => {
    setErreur(null);
    try {
      await envoyer(`/api/taches/${enc(tache.id)}/arreter`, { mode: 'ctrl-c' });
      rafraichir();
    } catch (e) {
      setErreur(e.message);
    }
  };

  return (
    <div className="grille" style={{ gap: 8, justifyItems: 'end' }}>
      {tache.arrets === 0 ? (
        <FuseButton label={entrainement ? 'Arrêter l’entraînement' : 'Arrêter'} undoLabel="Annuler l’arrêt" icon="stop" fuseColor="#d03b3b" undoWindow={3000} onCommit={arreter} />
      ) : (
        <FuseButton label="Interrompre sur-le-champ" undoLabel="Annuler" icon="croix" color="#b02e2e" background="#fbeaea" fuseColor="#d03b3b" undoWindow={3000} onCommit={arreter} />
      )}
      {tache.type === 'benchmark' && <span className="discret">Le bloc de test est déjà ouvert : l’interrompre le laisse ouvert sans rapport.</span>}
      {erreur && <Message genre="critique">{erreur}</Message>}
    </div>
  );
}
