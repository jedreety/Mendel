// Vos bots : une ligne par bot. Un clic ouvre sa page ; glisser la ligne vers la gauche montre ses actions :
// renommer, entrainer, supprimer. La suppression attend six secondes, le temps d'un « Annuler ».
import { useRef, useState } from 'react';
import { useDonnees } from '../donnees.jsx';
import { aller, lien } from '../route.js';
import { dateRun, duree, jourCourt, nombre, note } from '../format.js';
import { libellePaire, listeBots, nomBot, paire, periode, renommer, supprimerBot, useSuppressions } from '../bots.js';
import { Carte, EnTete, Icone, Message, Vide } from '../composants/Base.jsx';
import { notifier } from '../composants/Notifications.jsx';
import Chargement from '../composants/Chargement.jsx';
import { ACCENT, TEXTE_2 } from '../palette.js';
import SwipeRow from '../reactbits/SwipeRow/SwipeRow.jsx';

function Mesure({ libelle, valeur }) {
  return (
    <span className="bot-mesure">
      <span>{libelle}</span>
      <span>{valeur}</span>
    </span>
  );
}

function Contenu({ bot, occupe }) {
  const creation = dateRun(bot.nom);
  return (
    <div className="bot-ligne">
      <span className="bot-avatar">{paire(bot.symbole).base.slice(0, 4)}</span>
      <span className="liste-texte">
        <strong>{nomBot(bot)}</strong>
        <span>
          {libellePaire(bot.symbole)}
          {periode(bot) ? ` · ${periode(bot)}` : ''}
          {creation ? ` · créé le ${jourCourt(creation)}` : ''}
        </span>
      </span>
      <span className="bot-mesures">
        {occupe ? <span className="etiquette accent">en entraînement</span> : bot.rapport ? <span className="etiquette bon">benchmark fait</span> : null}
        <Mesure libelle="générations" valeur={nombre(bot.generation)} />
        <Mesure libelle="meilleure note" valeur={note(bot.meilleure_note)} />
        <Mesure libelle="entraînement" valeur={duree(bot.duree_totale_s)} />
      </span>
    </div>
  );
}

function Renommer({ bot, fermer }) {
  const [valeur, setValeur] = useState(nomBot(bot));
  const [envoi, setEnvoi] = useState(false);
  const enregistrer = async e => {
    e.preventDefault();
    setEnvoi(true);
    try {
      await renommer(bot.nom, valeur);
      fermer();
    } catch (err) {
      notifier({ genre: 'critique', titre: 'Nom refusé', texte: err.message });
      setEnvoi(false);
    }
  };
  return (
    <Carte>
      <form className="renommer" onSubmit={enregistrer}>
        <input className="saisie" autoFocus value={valeur} maxLength={60} placeholder="Vide : son nom par défaut" onChange={e => setValeur(e.target.value)} onKeyDown={e => e.key === 'Escape' && fermer()} aria-label="Nouveau nom" />
        <button className="bouton primaire" disabled={envoi}>
          Enregistrer
        </button>
        <button type="button" className="bouton" onClick={fermer}>
          Annuler
        </button>
      </form>
    </Carte>
  );
}

// Un clic ouvre le bot, sauf s'il suivait un glissement, visait une action, ou refermait la ligne.
function LigneBot({ bot, occupe, renommerCe }) {
  const depart = useRef(null);
  const ouvrir = () => aller(['bots', bot.nom]);
  const actions = [
    { id: 'supprimer', label: 'Supprimer', onSelect: () => supprimerBot(bot.nom, nomBot(bot)) },
    { id: 'entrainer', label: 'Entraîner', color: ACCENT, icon: <Icone nom="eclair" taille={18} />, onSelect: () => aller(['entrainement', 'continuer'], { bot: bot.nom }) },
    { id: 'renommer', label: 'Renommer', color: TEXTE_2, icon: <Icone nom="crayon" taille={18} />, onSelect: renommerCe }
  ];
  if (occupe) {
    return (
      <div className="carte cliquable" style={{ padding: '0 18px', height: 80, display: 'flex' }} onClick={ouvrir}>
        <Contenu bot={bot} occupe />
      </div>
    );
  }
  return (
    <div
      onPointerDown={e => {
        const ligne = e.currentTarget.querySelector('.swipe-row');
        depart.current = { x: e.clientX, y: e.clientY, ouverte: ligne?.hasAttribute('data-open') };
      }}
      onClick={e => {
        const d = depart.current;
        if (!d || d.ouverte || e.target.closest('.swipe-row__action, .swipe-row__toggle')) return;
        if (Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) ouvrir();
      }}
      style={{ cursor: 'pointer' }}
    >
      <SwipeRow actions={actions} height={80} radius={18} actionWidth={92} label={nomBot(bot)} onCommit={() => {}}>
        <Contenu bot={bot} />
      </SwipeRow>
    </div>
  );
}

export default function Bots() {
  const { runs, tache, pret } = useDonnees();
  const supprimes = useSuppressions();
  const [enEdition, setEnEdition] = useState(null);
  const bots = listeBots(runs).filter(b => !supprimes.has(b.nom));
  const orphelins = runs.filter(r => r.source && !runs.some(x => x.nom === r.source) && !supprimes.has(r.nom));
  const occupe = b => !!tache && (tache.run === b.nom || tache.source === b.nom || runs.some(r => r.source === b.nom && r.nom === tache.run));
  return (
    <>
      <EnTete
        surtitre={<span className="oeil">Bots</span>}
        titre="Vos bots"
        description="Chaque bot apprend sur un seul marché. Cliquez sur un bot pour tout savoir de lui ; glissez sa ligne vers la gauche pour le renommer, l’entraîner ou le supprimer."
        actions={
          <a className="bouton primaire grand" href="#/entrainement/nouveau">
            <Icone nom="plus" taille={15} />
            Nouveau bot
          </a>
        }
      />
      {!pret.runs ? (
        <Chargement texte="Lecture des bots" />
      ) : bots.length ? (
        <div className="liste-bots">
          {bots.map(b => (enEdition === b.nom ? <Renommer key={b.nom} bot={b} fermer={() => setEnEdition(null)} /> : <LigneBot key={b.nom} bot={b} occupe={occupe(b)} renommerCe={() => setEnEdition(b.nom)} />))}
        </div>
      ) : (
        <Carte>
          <Vide titre="Aucun bot pour l’instant">
            Un bot naît d’un premier entraînement.
            <a className="bouton primaire" href="#/entrainement/nouveau">
              Créer un bot
            </a>
          </Vide>
        </Carte>
      )}
      {orphelins.length > 0 && (
        <Message>
          {orphelins.length} run{orphelins.length > 1 ? 's' : ''} témoin{orphelins.length > 1 ? 's' : ''} sans bot :{' '}
          {orphelins.map((r, i) => (
            <span key={r.nom}>
              {i > 0 && ', '}
              <a className="lien" href={lien(['bots', r.nom])}>
                {r.nom}
              </a>
            </span>
          ))}
          . Leur bot a été supprimé ou déplacé.
        </Message>
      )}
    </>
  );
}
