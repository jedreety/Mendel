// Entrainement en direct : ce que fait le bot en ce moment, en clair. Temps ecoule, generations faites,
// progression, puis le grand graphique, au choix, et ce qui aide a le lire. Tout vient de generations.jsonl,
// de config.toml et du flux du serveur : rien ne gene le bot. Au demarrage, avant la premiere generation, une
// ligne suit les etapes que le bot ecrit dans sa sortie.
import { useMemo, useState } from 'react';
import { useConfig, useDonnees, useGenerations, useJournal, useMaintenant } from '../../donnees.jsx';
import { lien } from '../../route.js';
import { argent, duree, heure, jourCourt, nombre, note, pct, signe } from '../../format.js';
import { annee, libellePaire, nomRun, paire, periode } from '../../bots.js';
import { Chiffre, EnTete, EnTeteCarte, Icone, Message, Progression, Segments } from '../../composants/Base.jsx';
import Arret from '../../composants/Arret.jsx';
import Journal from '../../composants/Journal.jsx';
import Poste from '../../composants/Poste.jsx';
import { GraphArgent, GraphCriteres, GraphNotes } from '../../graphiques/Evolution.jsx';
import AnimatedList from '../../reactbits/AnimatedList/AnimatedList.jsx';
import StatusMark from '../../reactbits/StatusMark/StatusMark.jsx';
import ThoughtLine from '../../reactbits/ThoughtLine/ThoughtLine.jsx';

const JOUR = 86400;
const GRAPHIQUES = [
  { cle: 'notes', libelle: 'Les notes' },
  { cle: 'criteres', libelle: 'Les critères' },
  { cle: 'argent', libelle: 'L’argent des bots' }
];

// Le grand graphique, au choix : les notes, les criteres de la note du meilleur bot, ou l'argent des bots.
function GrandGraphique({ lignes, depart, config, cotation, groupe }) {
  const [vue, setVue] = useState('notes');
  const choix = <Segments elements={GRAPHIQUES} actif={vue} onChange={setVue} etiquette="Graphique affiché" taille="sm" />;
  const commun = { lignes, depart: depart || undefined, hauteur: 360, groupe, actions: choix };
  if (vue === 'criteres') return <GraphCriteres {...commun} poids={config?.poids_notation} />;
  if (vue === 'argent') return <GraphArgent {...commun} capital={config?.capital_initial} cotation={cotation} />;
  return <GraphNotes {...commun} />;
}

// Le demarrage, d'apres ce que le bot ecrit : donnees, tables des modules et calculs pour la GPU, puis premiere
// generation.
function Demarrage({ tache }) {
  const { texte } = useJournal(tache.id);
  const etapes = ['Données, tables des modules et calculs pour la GPU'];
  if (/^Run /m.test(texte)) etapes.push('Première génération');
  return (
    <div className="carte" style={{ padding: '20px 24px' }}>
      <ThoughtLine label="Le bot démarre" steps={etapes} collapsible={false} fontSize={15} glyph="sparkle" glyphColor="#2a78d6" />
      <p className="discret">Comptez une demi-minute à une minute. Il apparaît ici dès sa première génération.</p>
    </div>
  );
}

function Avancement({ tache, run, lignes }) {
  const maintenant = useMaintenant();
  const derniere = lignes[lignes.length - 1];
  const moyenne = run?.duree_moyenne_s;
  const depart = tache.depart ?? 0;
  if (!run) return null;
  const ecoule = derniere ? Math.max(0, maintenant - Date.parse(derniere.date) / 1000) : null;
  const partGeneration = moyenne && ecoule != null ? Math.min(0.97, ecoule / moyenne) : null;
  if (tache.objectif) {
    const total = Math.max(1, tache.objectif - depart);
    const faites = run.generation - depart;
    const reste = moyenne ? (tache.objectif - run.generation) * moyenne : null;
    return <Progression part={(faites + (partGeneration ?? 0)) / total} gauche={`Génération ${nombre(run.generation)} sur ${nombre(tache.objectif)}`} droite={tache.etat === 'arret demande' ? 'arrêt demandé' : reste != null ? `fin dans ${duree(reste)} environ` : ''} />;
  }
  return <Progression part={partGeneration} continu gauche={`Génération ${nombre(run.generation)} en cours`} droite={tache.etat === 'arret demande' ? 'arrêt demandé' : moyenne ? `une toutes les ${duree(moyenne)}` : ''} />;
}

// Les periodes du lot en cours sur la frise des annees d'entrainement.
function Periodes({ ligne, config }) {
  if (!ligne || !config) return null;
  const debut = Date.parse(config.debut_entrainement) / 1000;
  const fin = Date.parse(config.debut_validation) / 1000 - config.prechauffage_jours * JOUR;
  const largeur = fin - debut;
  return (
    <div className="grille" style={{ gap: 6 }}>
      <div className="fenetres" aria-hidden="true">
        {ligne.lot.fenetres.map(f => {
          const d = Date.parse(f.debut) / 1000;
          return <i key={f.nom} title={`${jourCourt(d)} → ${jourCourt(d + config.duree_fenetre_jours * JOUR)}`} style={{ left: `${((d - debut) / largeur) * 100}%`, width: `${((config.duree_fenetre_jours * JOUR) / largeur) * 100}%` }} />;
        })}
      </div>
      <div className="fenetres-axe">
        <span>{annee(config.debut_entrainement)}</span>
        <span>{annee(config.debut_validation) - 1}</span>
      </div>
    </div>
  );
}

// Records et nouveaux lots, du plus recent au plus ancien.
function Evenements({ lignes }) {
  const liste = useMemo(() => {
    const e = [];
    let meilleure = -Infinity;
    let lot = null;
    for (const l of lignes) {
      if (l.meilleure_note_pantheon > meilleure) {
        if (meilleure > -Infinity) e.push({ g: l.generation, icone: 'etincelle', texte: `Nouveau record : ${note(l.meilleure_note_pantheon)}` });
        meilleure = l.meilleure_note_pantheon;
      }
      if (lot !== null && l.lot.numero !== lot) e.push({ g: l.generation, icone: 'rafraichir', texte: 'Nouvelles périodes d’entraînement tirées' });
      lot = l.lot.numero;
    }
    return e.reverse().slice(0, 8);
  }, [lignes]);
  if (!liste.length) return <p className="discret">Les records et les nouvelles périodes s’afficheront ici.</p>;
  return (
    <AnimatedList
      label="Événements"
      items={liste}
      getKey={e => `${e.icone}-${e.g}`}
      maxHeight={300}
      renderItem={e => (
        <div className="ligne" style={{ flexWrap: 'nowrap', gap: 12 }}>
          <Icone nom={e.icone} />
          <span className="liste-texte">
            <strong style={{ fontWeight: 560 }}>{e.texte}</strong>
          </span>
          <span className="discret">gén. {e.g}</span>
        </div>
      )}
    />
  );
}

function AutreTache({ tache, runs }) {
  const maintenant = useMaintenant();
  const run = runs.find(r => r.nom === tache.run);
  const titres = { benchmark: `Benchmark de « ${run ? nomRun(run, runs) : tache.run} »`, verifier: 'Vérification des noyaux', donnees: `Téléchargement de ${tache.symbole ?? 'données'}` };
  const textes = {
    benchmark: 'Le bot et ses références passent le bloc de test, trimestre par trimestre, puis leurs trades sont rejoués dans le moteur exact. À la fin, ses trades se regardent dans l’onglet Benchmark du bot.',
    verifier: 'Les calculs de la GPU sont comparés à leurs références et au moteur exact, sur l’entraînement et la validation seulement.',
    donnees: 'Les barres horaires mensuelles arrivent de data.binance.vision, puis le fichier du marché est préparé.'
  };
  return (
    <>
      <EnTete surtitre={<span className="oeil">En cours</span>} titre={titres[tache.type] ?? tache.type} description={textes[tache.type]} actions={<Arret tache={tache} />} />
      <div className="chiffres">
        <Chiffre libelle="Temps écoulé" icone="horloge" valeur={duree(maintenant - Date.parse(tache.debut) / 1000)} detail={`lancé à ${heure(tache.debut)} UTC`} />
        <div className="chiffre" style={{ alignContent: 'center' }}>
          <StatusMark status="running" label={tache.etat === 'arret demande' ? 'Arrêt demandé' : 'En cours'} />
        </div>
      </div>
      <section className="section">
        <EnTeteCarte titre="Sortie de la tâche" description="Comme dans son terminal." />
        <Journal tacheId={tache.id} hauteur={440} />
      </section>
      {tache.type === 'benchmark' && run && (
        <p className="discret">
          Ensuite : <a className="lien" href={lien(['bots', run.nom, 'benchmark'])}>le benchmark du bot</a>.
        </p>
      )}
    </>
  );
}

export default function Direct({ tache }) {
  const { runs } = useDonnees();
  const maintenant = useMaintenant();
  const run = runs.find(r => r.nom === tache.run);
  const { lignes } = useGenerations(tache.run);
  const config = useConfig(tache.run ?? null)?.valeurs;

  if (!['nouveau', 'reprendre', 'a-blanc', 'hasard'].includes(tache.type)) return <AutreTache tache={tache} runs={runs} />;

  const depart = tache.depart ?? 0;
  const faites = run ? run.generation - depart : 0;
  const avant = lignes.filter(l => l.generation < depart);
  const noteAvant = avant.length ? avant[avant.length - 1].meilleure_note_pantheon : null;
  const derniere = lignes[lignes.length - 1];
  const { cotation } = paire(run?.symbole);
  const temoin = tache.type === 'a-blanc' || tache.type === 'hasard';
  const nom = run ? nomRun(run, runs) : tache.nom || 'Nouveau bot';
  const prochainLot = config?.renouvellement_lot && run ? config.renouvellement_lot - (run.generation % config.renouvellement_lot) : null;
  const [fraisMin, fraisMax] = config?.frais_entrainement ?? [];

  return (
    <>
      <EnTete
        surtitre={
          <>
            <span className="point vivant" />
            <span className="oeil" style={{ color: 'var(--bon-texte)' }}>
              {tache.etat === 'arret demande' ? 'Arrêt demandé' : 'En direct'}
            </span>
            {run && <span className="etiquette accent">{libellePaire(run.symbole)}</span>}
            {run && periode(run) && <span className="etiquette">{periode(run)}</span>}
            <span className="etiquette">{tache.objectif ? `${nombre(tache.objectif - depart)} générations` : 'en boucle'}</span>
            {temoin && <span className="etiquette alerte">{tache.type === 'a-blanc' ? 'prix mélangés' : 'sans évolution'}</span>}
          </>
        }
        titre={nom}
        description={
          temoin
            ? tache.type === 'a-blanc'
              ? 'Le même entraînement, mêmes graines, sur des prix mélangés année par année : ce qu’il trouve, c’est la note du hasard.'
              : 'Le même nombre de générations, mais chacune tirée au hasard : ce que le même budget obtient sans évolution.'
            : 'Chaque génération, des milliers de bots sont notés sur des périodes tirées dans les années d’entraînement ; les meilleurs font des enfants, et les meilleurs de tous passent en validation.'
        }
        actions={<Arret tache={tache} />}
      />

      {!run && <Demarrage tache={tache} />}

      <div className="chiffres">
        <Chiffre libelle="Temps écoulé" icone="horloge" valeur={duree(maintenant - Date.parse(tache.debut) / 1000)} detail={`lancé à ${heure(tache.debut)} UTC`} />
        <Chiffre libelle={tache.objectif ? 'Générations' : 'Répétitions'} icone="boucle" aide="generation" valeur={nombre(faites)} detail={tache.objectif ? `sur ${nombre(tache.objectif - depart)} prévues` : depart ? `depuis la reprise, ${nombre(run?.generation)} en tout` : 'jusqu’à ce que vous l’arrêtiez'} />
        <Chiffre libelle="Meilleure note" icone="etincelle" aide="noteValidation" valeur={note(run?.meilleure_note)} detail={noteAvant != null && run?.meilleure_note != null ? (run.meilleure_note > noteAvant ? `${signe(run.meilleure_note - noteAvant, 4)} depuis la reprise` : 'pas encore de record depuis la reprise') : run?.generation_meilleure != null ? `trouvée à la génération ${run.generation_meilleure}` : 'en attente de la première génération'} />
        <Chiffre libelle="Bots essayés" icone="bot" valeur={run ? nombre(run.bots_evalues) : '–'} detail={run?.duree_moyenne_s ? `${nombre(run.population / run.duree_moyenne_s)} par seconde` : null} />
      </div>

      <Avancement tache={tache} run={run} lignes={lignes} />

      {tache.etat === 'arret demande' && <Message genre="alerte">Arrêt demandé : le bot finit sa génération, écrit son point de sauvegarde, puis rejoue son Panthéon dans le moteur exact. Il pourra reprendre exactement ici.</Message>}

      <div className="carte">
        <GrandGraphique lignes={lignes} depart={depart} config={config} cotation={cotation} groupe={`direct-${tache.run}`} />
      </div>

      <div className="grille grille-3" style={{ gap: 32 }}>
        <section className="section">
          <EnTeteCarte titre="Son champion" aide="champion" />
          {run?.champion ? (
            <dl className="cles-valeurs">
              <dt>Bot</dt>
              <dd className="mono">{run.champion.id}</dd>
              <dt>Note</dt>
              <dd>
                {note(run.champion.note)}, génération {run.generation_meilleure}
              </dd>
              <dt>Sans record</dt>
              <dd>{run.stagnation ? `depuis ${nombre(run.stagnation)} génération${run.stagnation > 1 ? 's' : ''}` : 'record à la dernière génération'}</dd>
            </dl>
          ) : (
            <p className="discret">Il apparaît à la fin de la première génération.</p>
          )}
        </section>
        <section className="section">
          <EnTeteCarte titre="Ce qu’il étudie" aide="lot" />
          <p className="second" style={{ fontSize: 13 }}>
            {derniere && config
              ? `${derniere.lot.fenetres.length} périodes de ${config.duree_fenetre_jours} jours, tirées au hasard entre ${annee(config.debut_entrainement)} et ${annee(config.debut_validation) - 1}. Tous les bots voient les mêmes.`
              : 'Les périodes s’affichent à la fin de la première génération.'}
            {prochainLot != null && derniere ? ` Nouvelles périodes dans ${prochainLot} génération${prochainLot > 1 ? 's' : ''}.` : ''}
          </p>
          <Periodes ligne={derniere} config={config} />
        </section>
        <section className="section">
          <EnTeteCarte titre="L’argent en jeu" aide="population" />
          <p className="second" style={{ fontSize: 13 }}>
            {config ? (
              <>
                Chaque bot trade avec <strong>{argent(config.capital_initial, cotation)} fictifs</strong> sur chaque période, et paie {fraisMin != null ? `${pct(Number(fraisMin), 2)} à ${pct(Number(fraisMax), 2)}` : 'des frais'} par ordre, plus un glissement. Soit {nombre(config.population * config.fenetres_par_lot)} comptes fictifs à chaque génération ; aucun argent réel.
              </>
            ) : (
              '–'
            )}
          </p>
        </section>
      </div>

      <hr className="filet" />

      <div className="grille grille-2" style={{ gap: 40 }}>
        <section className="section">
          <EnTeteCarte titre="Événements" description="Records de validation et nouvelles périodes." />
          <Evenements lignes={lignes} />
        </section>
        <section className="section">
          <EnTeteCarte
            titre="La machine"
            description="Mesurée toutes les deux secondes."
            actions={
              <a className="fleche-lien" href="#/systeme/poste">
                Historique
                <Icone nom="fleche" taille={14} />
              </a>
            }
          />
          <Poste />
        </section>
      </div>

      <details className="avances">
        <summary>
          <Icone nom="terminal" />
          Sortie brute du bot
          <span className="discret" style={{ fontWeight: 400 }}>
            comme dans son terminal
          </span>
        </summary>
        <div className="avances-contenu">
          <Journal tacheId={tache.id} hauteur={360} />
        </div>
      </details>
    </>
  );
}
