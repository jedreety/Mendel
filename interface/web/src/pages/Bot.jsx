// Page d'un bot : retour a la liste en haut a gauche, son nom (un clic le renomme) et son action principale, puis
// quatre vues : resume, evolution, benchmark, details. La suppression est dans les details. Un temoin (run a
// blanc, recherche aleatoire) a la meme page, sans benchmark, et renvoie a son bot.
import { useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { envoyer } from '../api.js';
import { useDetail, useDonnees } from '../donnees.jsx';
import { aller, lien, lienTache } from '../route.js';
import { VUES_BOT } from '../navigation.js';
import { dateRun, duree, jour, nombre } from '../format.js';
import { libellePaire, nomBot, nomRun, periode, renommer, useSuppressions } from '../bots.js';
import { EnTete, Icone, Message, Segments } from '../composants/Base.jsx';
import { notifier } from '../composants/Notifications.jsx';
import Chargement from '../composants/Chargement.jsx';
import Resume from './bot/Resume.jsx';
import Evolution from './bot/Evolution.jsx';
import Benchmark from './bot/Benchmark.jsx';
import Details from './bot/Details.jsx';

function FormNom({ run, fermer }) {
  const [valeur, setValeur] = useState(nomBot(run));
  const enregistrer = async e => {
    e.preventDefault();
    try {
      await renommer(run.nom, valeur);
      fermer();
    } catch (err) {
      notifier({ genre: 'critique', titre: 'Nom refusé', texte: err.message });
    }
  };
  return (
    <form className="renommer" onSubmit={enregistrer} style={{ maxWidth: 560 }}>
      <input className="saisie grande" autoFocus value={valeur} maxLength={60} placeholder="Vide : son nom par défaut" onChange={e => setValeur(e.target.value)} onKeyDown={e => e.key === 'Escape' && fermer()} aria-label="Nouveau nom" />
      <button className="bouton primaire">Enregistrer</button>
      <button type="button" className="bouton" onClick={fermer}>
        Annuler
      </button>
    </form>
  );
}

export default function Bot({ nom, vue }) {
  const { runs, tache, pret, rafraichir } = useDonnees();
  const supprimes = useSuppressions();
  const { detail, erreur } = useDetail(nom);
  const [renommage, setRenommage] = useState(false);
  const reduit = useReducedMotion();
  const run = runs.find(r => r.nom === nom);

  if (supprimes.has(nom) || (pret.runs && !run)) {
    return (
      <>
        <EnTete retour="#/bots" titre={supprimes.has(nom) ? 'Suppression en cours' : 'Ce bot n’existe plus'} description={supprimes.has(nom) ? 'Il part à la corbeille avec ses témoins.' : erreur ?? 'Il a peut-être été supprimé.'} />
      </>
    );
  }
  if (!run) return <Chargement texte="Lecture du bot" minHauteur={320} />;

  const temoin = run.mode !== 'reel';
  const source = temoin ? runs.find(r => r.nom === run.source) : null;
  const temoins = runs.filter(r => r.source === run.nom);
  const occupe = !!tache && (tache.run === nom || tache.source === nom || temoins.some(t => t.nom === tache.run));
  const vues = VUES_BOT.filter(v => !temoin || v.cle !== 'benchmark');
  const actuelle = vues.some(v => v.cle === vue) ? vue : 'resume';
  const creation = dateRun(run.nom);
  const incomplet = temoin && run.point_de_sauvegarde && run.generations_max != null && run.generation < run.generations_max;

  const reprendreTemoin = async () => {
    try {
      await envoyer('/api/taches', { type: 'reprendre', run: nom });
      rafraichir();
      aller(['entrainement']);
    } catch (e) {
      notifier({ genre: 'critique', titre: 'Reprise refusée', texte: e.message });
    }
  };

  const actions = occupe ? (
    <a className="bouton primaire grand" href={lienTache(tache)}>
      <Icone nom="lecture" taille={15} />
      Suivre en direct
    </a>
  ) : !temoin ? (
    <a className="bouton primaire grand" href={lien(['entrainement', 'continuer'], { bot: nom })} aria-disabled={!run.point_de_sauvegarde || run.actif}>
      <Icone nom="eclair" taille={15} />
      Entraîner encore
    </a>
  ) : incomplet ? (
    <button className="bouton primaire grand" onClick={reprendreTemoin} disabled={!!tache || run.actif}>
      Reprendre
    </button>
  ) : null;

  const titreBot = temoin ? (
    nomRun(run, runs)
  ) : (
    <button type="button" className="titre-editable" onClick={() => setRenommage(true)} title="Renommer">
      {nomRun(run, runs)}
      <Icone nom="crayon" taille={18} />
    </button>
  );

  return (
    <>
      <EnTete
        retour={temoin && source ? lien(['bots', source.nom, 'benchmark']) : '#/bots'}
        surtitre={
          <>
            <span className="etiquette accent">{libellePaire(run.symbole)}</span>
            {periode(run) && <span className="etiquette">apprend {periode(run)}</span>}
            {temoin && <span className="etiquette alerte">{run.mode === 'a-blanc' ? 'run à blanc' : 'recherche aléatoire'}</span>}
            {occupe ? <span className="etiquette accent">en entraînement</span> : run.actif ? <span className="etiquette">écrit à l’instant</span> : null}
            {run.rapport && <span className="etiquette bon">benchmark fait</span>}
          </>
        }
        titre={renommage ? <FormNom run={run} fermer={() => setRenommage(false)} /> : titreBot}
        description={
          temoin ? (
            <>
              Témoin de{' '}
              {source ? (
                <a className="lien" href={lien(['bots', source.nom])}>
                  « {nomBot(source)} »
                </a>
              ) : (
                run.source
              )}{' '}
              : {run.mode === 'a-blanc' ? 'le même entraînement sur des prix mélangés.' : 'le même budget, sans évolution.'}
            </>
          ) : (
            `Créé le ${creation ? jour(creation) : '–'} · ${nombre(run.generation)} générations · ${duree(run.duree_totale_s)} d’entraînement`
          )
        }
        actions={!renommage && actions}
      />
      <div className="vues">
        <Segments elements={vues.map(v => ({ cle: v.cle, libelle: v.libelle, icone: v.icone, href: lien(['bots', nom, v.cle]) }))} actif={actuelle} etiquette="Vues du bot" />
      </div>
      {erreur && !detail && <Message genre="critique">{erreur}</Message>}
      {run.actif && !occupe && <Message genre="alerte">Ce bot a été écrit il y a moins de cinq minutes, peut-être depuis un terminal : son Panthéon se lit quand il est à l’arrêt.</Message>}
      <motion.div key={actuelle} className="vue" initial={reduit ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}>
        {actuelle === 'evolution' ? (
          <Evolution run={run} />
        ) : actuelle === 'benchmark' ? (
          <Benchmark run={run} detail={detail} />
        ) : actuelle === 'details' ? (
          <Details run={run} detail={detail} source={source} />
        ) : (
          <Resume run={run} detail={detail} />
        )}
      </motion.div>
    </>
  );
}
