// Accueil : ou vous en etiez, en quelques phrases, la suite en un bouton et la barre de commande ; puis un bandeau
// qui defile avec les chiffres des bots, vos bots et l'activite recente.
import { useEffect, useMemo, useState } from 'react';
import { enc, lire } from '../api.js';
import { useDonnees, useMaintenant } from '../donnees.jsx';
import { aller, lien, lienTache } from '../route.js';
import { duree, ilya, nombre, note, pctSigne } from '../format.js';
import { protocole } from '../protocole.js';
import { libellePaire, listeBots, nomBot, nomRun, paire, periode, useSuppressions } from '../bots.js';
import { ENTRAINEMENTS, STATUTS, raconter } from '../taches.js';
import { Icone, Progression, Vide } from '../composants/Base.jsx';
import { BarreCommande } from '../composants/Commande.jsx';
import StatusMark from '../reactbits/StatusMark/StatusMark.jsx';
import AnimatedList from '../reactbits/AnimatedList/AnimatedList.jsx';
import GlareHover from '../reactbits/GlareHover/GlareHover.jsx';
import ScrollVelocity from '../reactbits/ScrollVelocity/ScrollVelocity.jsx';

const jourLong = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });

function EnCours({ tache, runs }) {
  const maintenant = useMaintenant();
  const run = runs.find(r => r.nom === tache.run);
  const depuis = ilya(tache.debut, maintenant).replace('il y a ', '');
  const { titre } = raconter(tache, runs);
  if (!ENTRAINEMENTS.includes(tache.type)) {
    return (
      <>
        <h1 className="bienvenue">{titre} en cours</h1>
        <p className="resume-texte">Lancé {ilya(tache.debut, maintenant)}. {tache.type === 'benchmark' ? 'Le bot découvre des données qu’il n’a jamais vues.' : 'Sa sortie s’affiche en direct.'}</p>
      </>
    );
  }
  const depart = tache.depart ?? 0;
  const objectif = tache.objectif;
  const faites = run ? run.generation - depart : 0;
  return (
    <>
      <h1 className="bienvenue">{run ? `« ${nomRun(run, runs)} » s’entraîne` : 'Un entraînement démarre'}</h1>
      <p className="resume-texte">
        {run ? (
          <>
            Depuis <strong>{depuis}</strong>, il a fait <strong>{nombre(faites)} génération{faites > 1 ? 's' : ''}</strong>
            {objectif ? ` sur ${nombre(objectif - depart)}` : ', en boucle jusqu’à ce que vous l’arrêtiez'}. Sa meilleure note de validation est de <strong>{note(run.meilleure_note)}</strong>.
          </>
        ) : (
          'Le bot charge ses données, compile ses calculs pour la GPU et évalue sa population de référence. Il apparaît dans quelques secondes.'
        )}
      </p>
      {run && objectif ? (
        <div style={{ maxWidth: 560 }}>
          <Progression part={faites / Math.max(1, objectif - depart)} gauche={`Génération ${run.generation}`} droite={`${Math.round((faites / Math.max(1, objectif - depart)) * 100)} %`} />
        </div>
      ) : null}
    </>
  );
}

function Resultat({ run }) {
  const [rapport, setRapport] = useState(null);
  useEffect(() => {
    if (!run?.rapport) return;
    lire(`/api/runs/${enc(run.nom)}/rapport`).then(setRapport).catch(() => {});
  }, [run?.nom, run?.rapport]);
  const c = rapport?.bots?.champion;
  const bh = rapport?.bots?.['buy and hold'];
  if (!c) return null;
  return (
    <>
      {' '}
      Sur des données jamais vues, il a fait <strong>{pctSigne(c.rendement_chaine)}</strong>
      {bh ? (
        <>
          {' '}
          quand acheter et garder faisait <strong>{pctSigne(bh.rendement_chaine)}</strong>
        </>
      ) : null}
      , en {nombre(c.trades)} trades.
    </>
  );
}

function OuVousEnEtiez({ tache, taches, runs }) {
  const maintenant = useMaintenant(10000);
  if (tache) return <EnCours tache={tache} runs={runs} />;
  const derniere = taches[0];
  const bots = listeBots(runs);
  if (!derniere) {
    const b = bots[0];
    return (
      <>
        <h1 className="bienvenue">{b ? 'Bon retour' : 'Bienvenue'}</h1>
        <p className="resume-texte">{b ? `Votre dernier bot est « ${nomBot(b)} », entraîné sur ${libellePaire(b.symbole)} : ${nombre(b.generation)} générations, meilleure note ${note(b.meilleure_note)}.` : 'Un bot apprend à trader sur un seul marché, en faisant évoluer des milliers de candidats sur la GPU. Commencez par en créer un.'}</p>
      </>
    );
  }
  const run = runs.find(r => r.nom === (derniere.source ?? derniere.run));
  const bot = run && (run.source ? runs.find(r => r.nom === run.source) : run);
  const { titre, issue } = raconter(derniere, runs);
  return (
    <>
      <h1 className="bienvenue">Voici où vous en étiez</h1>
      <p className="resume-texte">
        Dernière activité {ilya(derniere.fin ?? derniere.debut, maintenant)} : <strong>{titre.charAt(0).toLowerCase() + titre.slice(1)}</strong>, {issue}.
        {derniere.type === 'benchmark' && bot ? <Resultat run={bot} /> : null}
        {bot && bot.mode === 'reel' ? ` ${protocole(bot).suite.texte}` : null}
      </p>
    </>
  );
}

function Actions({ tache, taches, runs }) {
  if (tache) {
    return (
      <a className="bouton primaire grand" href={lienTache(tache)}>
        <Icone nom="lecture" taille={15} />
        Suivre en direct
      </a>
    );
  }
  const derniere = taches[0];
  const run = derniere && runs.find(r => r.nom === (derniere.source ?? derniere.run));
  const bot = run && (run.source ? runs.find(r => r.nom === run.source) : run);
  const suite = bot?.mode === 'reel' ? protocole(bot).suite : null;
  return (
    <>
      {suite && (
        <a className="bouton primaire grand" href={suite.href}>
          {suite.action}
          <Icone nom="fleche" taille={15} />
        </a>
      )}
      <a className={`bouton grand ${suite ? '' : 'primaire'}`} href="#/entrainement/nouveau">
        <Icone nom="plus" taille={15} />
        Nouveau bot
      </a>
    </>
  );
}

// Le bandeau qui defile : les chiffres de chaque bot, comme un bandeau de cotations. Il accelere avec le defilement.
function Defilant({ bots }) {
  const texte = bots.length ? (
    bots.map(b => (
      <span key={b.nom}>
        <b>{nomBot(b)}</b> {libellePaire(b.symbole)} · note <b>{note(b.meilleure_note)}</b> · {nombre(b.generation)} générations · {duree(b.duree_totale_s)} de calcul
        {b.rapport ? ' · benchmark fait' : ''}
        <i />
      </span>
    ))
  ) : (
    <span>
      Une population de bots <i />
      des générations qui se succèdent <i />
      une année pour valider <i />
      un test qui ne s’ouvre qu’une fois <i />
    </span>
  );
  return (
    <div className="defilant" aria-hidden="true">
      <ScrollVelocity texts={[texte]} velocity={26} numCopies={4} velocityMapping={{ input: [0, 1000], output: [0, 3] }} />
    </div>
  );
}

function VosBots({ bots }) {
  if (!bots.length) {
    return (
      <Vide titre="Aucun bot entraîné">
        <a className="bouton primaire" href="#/entrainement/nouveau">
          Créer mon premier bot
        </a>
      </Vide>
    );
  }
  return (
    <div className="tuiles-bots">
      {bots.slice(0, 4).map(b => (
        <GlareHover key={b.nom}>
          <a className="tuile-bot" href={lien(['bots', b.nom])}>
            <span className="tuile-bot-tete">
              <span className="bot-avatar">{paire(b.symbole).base.slice(0, 4)}</span>
              <span className="liste-texte">
                <strong>{nomBot(b)}</strong>
                <span>
                  {libellePaire(b.symbole)}
                  {periode(b) ? ` · ${periode(b)}` : ''}
                </span>
              </span>
            </span>
            <span className="tuile-bot-note">
              <span className="discret">meilleure note</span>
              <b>{note(b.meilleure_note)}</b>
            </span>
            <span className="ligne" style={{ justifyContent: 'space-between' }}>
              <span className="discret">{nombre(b.generation)} générations</span>
              {b.rapport ? <span className="etiquette bon">benchmark fait</span> : b.actif ? <span className="etiquette accent">en cours</span> : null}
            </span>
          </a>
        </GlareHover>
      ))}
    </div>
  );
}

function Activite({ taches, runs }) {
  const maintenant = useMaintenant(10000);
  if (!taches.length) return <Vide titre="Rien pour l’instant">Chaque entraînement, benchmark ou téléchargement apparaîtra ici.</Vide>;
  const liste = taches.slice(0, 6);
  return (
    <AnimatedList
      label="Activité récente"
      items={liste}
      getKey={t => t.id}
      onItemSelect={t => {
        const bot = t.source ?? t.run;
        if (bot && runs.some(r => r.nom === bot)) aller(['bots', bot]);
        else aller(['systeme', 'taches']);
      }}
      renderItem={t => {
        const { titre, issue } = raconter(t, runs, !t.run || taches.find(x => x.run === t.run) === t);
        return (
          <div className="activite-ligne">
            <StatusMark status={STATUTS[t.etat] ?? 'pending'} size={20} />
            <span className="activite-texte">
              <strong>{titre}</strong>
              <span>{issue}</span>
            </span>
            <span className="discret">{ilya(t.fin ?? t.debut, maintenant)}</span>
          </div>
        );
      }}
    />
  );
}

export default function Accueil() {
  const { tache, taches, runs } = useDonnees();
  const supprimes = useSuppressions();
  const bots = useMemo(() => listeBots(runs).filter(b => !supprimes.has(b.nom)), [runs, supprimes]);
  const jour = jourLong.format(new Date());
  return (
    <>
      <section className="heros">
        <span className="oeil">{jour.charAt(0).toUpperCase() + jour.slice(1)}</span>
        <OuVousEnEtiez tache={tache} taches={taches} runs={runs} />
        <div className="ligne" style={{ gap: 10, marginTop: 4 }}>
          <Actions tache={tache} taches={taches} runs={runs} />
        </div>
        <div style={{ marginTop: 14 }}>
          <BarreCommande />
        </div>
      </section>
      <Defilant bots={bots} />
      <div className="grille grille-principale" style={{ gap: 40, alignItems: 'start' }}>
        <section className="section">
          <div className="carte-entete">
            <div>
              <h2>Vos bots</h2>
              {bots.length > 0 && <p>{`${bots.length} bot${bots.length > 1 ? 's' : ''}, ${duree(bots.reduce((s, b) => s + (b.duree_totale_s ?? 0), 0))} d’entraînement en tout`}</p>}
            </div>
            {bots.length > 0 && (
              <a className="fleche-lien" href="#/bots">
                Tous
                <Icone nom="fleche" taille={14} />
              </a>
            )}
          </div>
          <VosBots bots={bots} />
        </section>
        <section className="section">
          <div className="carte-entete">
            <div>
              <h2>Activité récente</h2>
            </div>
            <a className="fleche-lien" href="#/systeme/taches">
              Tout voir
              <Icone nom="fleche" taille={14} />
            </a>
          </div>
          <Activite taches={taches} runs={runs} />
        </section>
      </div>
    </>
  );
}
