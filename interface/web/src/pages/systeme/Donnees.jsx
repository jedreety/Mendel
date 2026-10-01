// Donnees : les marches disponibles (un fichier horaire par marche dans data/prepared/), et en ajouter un en
// telechargeant ses barres chez Binance (python -m scripts.fetch_binance, comme au terminal). En tete, un mur de
// marches qui defile : ceux qui sont la, et des marches courants a telecharger, qu'un clic place dans le formulaire.
import { useMemo, useRef, useState } from 'react';
import { envoyer } from '../../api.js';
import { useDonnees, useEffetsActifs, useMaintenant, useMarches } from '../../donnees.jsx';
import { annee, libellePaire, listeBots, paire } from '../../bots.js';
import { nombre, octets } from '../../format.js';
import { Carte, EnTeteCarte, Icone, Message, Vide } from '../../composants/Base.jsx';
import { notifier } from '../../composants/Notifications.jsx';
import Chargement from '../../composants/Chargement.jsx';
import DriftWall from '../../reactbits/DriftWall/DriftWall.jsx';

// Des marches courants chez Binance, cotes en USDT, pour qui veut en ajouter un.
const COURANTS = [
  ['ETHUSDT', 'Ethereum'],
  ['SOLUSDT', 'Solana'],
  ['BNBUSDT', 'BNB'],
  ['XRPUSDT', 'XRP'],
  ['ADAUSDT', 'Cardano'],
  ['DOGEUSDT', 'Dogecoin'],
  ['EURUSDT', 'Euro'],
  ['AVAXUSDT', 'Avalanche'],
  ['LINKUSDT', 'Chainlink'],
  ['DOTUSDT', 'Polkadot'],
  ['LTCUSDT', 'Litecoin'],
  ['TRXUSDT', 'TRON'],
  ['ATOMUSDT', 'Cosmos'],
  ['BTCUSDT', 'Bitcoin']
];
const TEINTES = ['#eef4ff', '#f3efff', '#ecfafd', '#fff1f6', '#f2f7ff', '#f6f2ff'];

function MurDesMarches({ marches, choisir }) {
  const effets = useEffetsActifs();
  const tuiles = useMemo(() => {
    const presents = new Set((marches ?? []).map(m => m.symbole));
    const liste = [...(marches ?? []).map(m => [m.symbole, 'déjà là', true]), ...COURANTS.filter(([sym]) => !presents.has(sym)).map(([sym, nom]) => [sym, nom, false])];
    return liste.map(([sym, nom, present], i) => ({
      title: libellePaire(sym),
      onClick: present ? undefined : () => choisir(sym),
      contenu: (
        <span className="tuile-marche" style={{ '--fond-tuile': TEINTES[i % TEINTES.length] }}>
          <strong>{libellePaire(sym)}</strong>
          <span>{present ? 'déjà là' : `${nom} · à ajouter`}</span>
        </span>
      )
    }));
  }, [marches, choisir]);
  if (!effets) return null;
  return (
    <div className="mur-marches">
      <DriftWall items={tuiles} ariaLabel="Marchés" columns={6} tileWidth={168} tileHeight={78} gap={14} radius={14} tilt={16} turn={-12} perspective={1100} depth={90} speed={14} variance={0.4} parallax={0.5} lift={36} fade={0.5} dim={0.9} pauseOnHover />
      <span className="mur-legende">Cliquez sur un marché pour le préparer au téléchargement</span>
    </div>
  );
}

const SYMBOLE = /^[A-Z0-9]{5,20}$/;

// Binance ne publie que des mois complets : le dernier est le mois precedent.
function moisPrecedent(secondes) {
  const d = new Date(secondes * 1000);
  const m = d.getUTCMonth();
  return m === 0 ? `${d.getUTCFullYear() - 1}-12` : `${d.getUTCFullYear()}-${String(m).padStart(2, '0')}`;
}

function Ajouter({ symbole, setSymbole, formulaire }) {
  const { tache, taches, rafraichir } = useDonnees();
  const maintenant = useMaintenant(60000);
  const [debut, setDebut] = useState('2018-01');
  const [fin, setFin] = useState(() => moisPrecedent(maintenant));
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const enCours = tache?.type === 'donnees' ? tache : null;
  const echec = !tache && taches[0]?.type === 'donnees' && ['echec', 'tuee', 'interrompue'].includes(taches[0].etat) ? taches[0] : null;
  const valide = SYMBOLE.test(symbole) && /^\d{4}-\d{2}$/.test(debut) && /^\d{4}-\d{2}$/.test(fin) && debut <= fin;
  const lancer = async e => {
    e.preventDefault();
    setEnvoi(true);
    setErreur(null);
    try {
      await envoyer('/api/taches', { type: 'donnees', symbole, debut, fin });
      rafraichir();
      notifier({ genre: 'actif', titre: `Téléchargement de ${symbole} lancé`, texte: 'Il apparaîtra dans la liste à la fin.', href: '#/systeme/taches' });
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };
  return (
    <Carte>
      <EnTeteCarte titre="Ajouter un marché" description="Les barres horaires au comptant de Binance, mois par mois, depuis data.binance.vision. Un bot a besoin d’au moins cinq années : une pour chauffer ses indicateurs, deux pour apprendre, une de validation et une de test." />
      <form ref={formulaire} className="grille" style={{ gap: 14 }} onSubmit={lancer}>
        <div className="champs">
          <label className="champ">
            <span className="champ-nom">Symbole chez Binance</span>
            <input className={`saisie ${SYMBOLE.test(symbole) ? '' : 'invalide'}`} value={symbole} onChange={e => setSymbole(e.target.value.toUpperCase().replace(/\s/g, ''))} placeholder="EURUSDT" />
            <small>EURUSDT : l’euro en dollars (USDT) ; ETHUSDT : l’ether ; BTCEUR : le bitcoin en euros.</small>
          </label>
          <label className="champ">
            <span className="champ-nom">Du mois</span>
            <input className="saisie" type="month" value={debut} onChange={e => setDebut(e.target.value)} />
          </label>
          <label className="champ">
            <span className="champ-nom">Au mois</span>
            <input className="saisie" type="month" value={fin} onChange={e => setFin(e.target.value)} />
            <small>Le mois en cours n’est pas encore publié.</small>
          </label>
        </div>
        {enCours && <Message>Téléchargement de {enCours.symbole} en cours : il apparaîtra dans la liste à la fin.</Message>}
        {echec && <Message genre="critique">Le téléchargement de {echec.symbole} a échoué : sa sortie dans Tâches dit pourquoi (symbole inconnu, mois absents…). Un fichier partiel peut rester dans data/prepared/ ; supprimez-le avant de réessayer.</Message>}
        {erreur && <Message genre="critique">{erreur}</Message>}
        <div className="ligne">
          <button className="bouton primaire" disabled={!valide || envoi || !!tache}>
            <Icone nom="telecharger" taille={15} />
            Télécharger
          </button>
          {tache && !enCours && <span className="discret">Une tâche tourne déjà : une seule à la fois.</span>}
        </div>
        <p className="discret">Un marché déjà présent n’est jamais remplacé d’ici : les bots qui l’utilisent gardent l’empreinte de son fichier.</p>
      </form>
    </Carte>
  );
}

export default function Donnees() {
  const { runs } = useDonnees();
  const marches = useMarches();
  const bots = listeBots(runs);
  const [symbole, setSymbole] = useState('EURUSDT');
  const formulaire = useRef(null);
  const choisir = useMemo(
    () => sym => {
      setSymbole(sym);
      formulaire.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    },
    []
  );
  return (
    <>
      <MurDesMarches marches={marches} choisir={choisir} />
      <Carte>
        <EnTeteCarte titre="Marchés disponibles" description="Un fichier de barres horaires par marché, dans data/prepared/. Un bot n’en connaît qu’un." />
        {!marches ? (
          <Chargement texte="Lecture des marchés" />
        ) : marches.length ? (
          <ul className="liste">
            {marches.map(m => {
              const n = bots.filter(b => b.donnees === m.donnees).length;
              return (
                <li key={m.donnees} className="liste-ligne">
                  <span className="bot-avatar">{paire(m.symbole).base.slice(0, 4)}</span>
                  <span className="liste-texte">
                    <strong>{libellePaire(m.symbole)}</strong>
                    <span>
                      {annee(m.premiere)} → {annee(m.derniere)} · {nombre(m.barres)} heures · {octets(m.octets)} · <span className="mono">{m.donnees}</span>
                    </span>
                  </span>
                  <span className="etiquette">{n ? `${n} bot${n > 1 ? 's' : ''}` : 'aucun bot'}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <Vide titre="Aucun marché">Téléchargez-en un ci-dessous.</Vide>
        )}
      </Carte>
      <Ajouter symbole={symbole} setSymbole={setSymbole} formulaire={formulaire} />
    </>
  );
}
