// Benchmark d'un bot : son champion passe une seule fois des donnees qu'il n'a jamais vues, sans
// rien apprendre, a cote d'un bot tire au hasard. Avant : le bloc de test ferme ; on tape son annee, puis on
// maintient le bouton, deux gestes voulus pour ce qui ne se rattrape pas. Pendant : la tache, ici meme. Apres : la
// seance de test rejouee comme un film, puis le verdict.
import { useEffect, useState } from 'react';
import { enc, envoyer, lire } from '../../api.js';
import { useDiffere, useDonnees, useEffetsActifs, useMaintenant } from '../../donnees.jsx';
import { annee, paire } from '../../bots.js';
import { decimal, nombre, pct, pctSigne, quand } from '../../format.js';
import { protocole } from '../../protocole.js';
import { Carte, EnTeteCarte, Icone, Message, Progression, Vide } from '../../composants/Base.jsx';
import Arret from '../../composants/Arret.jsx';
import Chargement from '../../composants/Chargement.jsx';
import Journal from '../../composants/Journal.jsx';
import { ACCENT, PASTELS } from '../../palette.js';
import Prism from '../../reactbits/Prism/Prism.jsx';
import PrismaticBurst from '../../reactbits/PrismaticBurst/PrismaticBurst.jsx';
import CodeSlots from '../../reactbits/CodeSlots/CodeSlots.jsx';
import HoldButton from '../../reactbits/HoldButton/HoldButton.jsx';
import DepthText from '../../reactbits/DepthText/DepthText.jsx';
import LatticeLoader from '../../reactbits/LatticeLoader/LatticeLoader.jsx';
import Seance from './Seance.jsx';
import Trades, { NOMS_REFERENCES } from './Trades.jsx';

const ORDRE = ['champion', 'champion aleatoire', 'champion a blanc', 'champion de la recherche aleatoire', 'buy and hold'];
const NOMS = { ...Object.fromEntries(Object.entries(NOMS_REFERENCES).map(([k, v]) => [k.replace(/_/g, ' '), v])), 'buy and hold': 'Acheter et garder' };
const ECHECS = ['echec', 'tuee', 'interrompue'];
const ECLAT = [PASTELS.bleu, PASTELS.lavande, PASTELS.ciel];

// La seance ne se joue d'elle-meme qu'une fois par navigateur : ensuite, la vue d'ensemble et « Revoir ».
const CLE_VUE = nom => `seance-vue:${nom}`;
function dejaVue(nom) {
  try {
    return localStorage.getItem(CLE_VUE(nom)) === '1';
  } catch {
    return false;
  }
}
function marquerVue(nom) {
  try {
    localStorage.setItem(CLE_VUE(nom), '1');
  } catch {
    /* stockage indisponible : la seance se rejouera a la prochaine visite */
  }
}

function Ouverture({ run }) {
  const { tache, rafraichir } = useDonnees();
  const differe = useDiffere();
  const effets = useEffetsActifs() && differe;
  const [code, setCode] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState(null);
  const { benchmark, suite } = protocole(run);
  const attendu = String(annee(run.debut_test) ?? '');
  const statut = code.length < 4 ? 'idle' : code === attendu ? 'success' : 'error';
  const lancer = async () => {
    setEnvoi(true);
    setErreur(null);
    try {
      await envoyer('/api/taches', { type: 'benchmark', run: run.nom, confirmation: run.nom });
      rafraichir();
    } catch (e) {
      setErreur(e.message);
    } finally {
      setEnvoi(false);
    }
  };
  return (
    <section className="coffre">
      <div className="coffre-contenu">
        <span className="oeil ligne" style={{ gap: 6 }}>
          <Icone nom="verrou" taille={13} /> Bloc de test fermé
        </span>
        <h2 className="bienvenue" style={{ fontSize: 30 }}>
          Des données qu’il n’a jamais vues
        </h2>
        <p className="resume-texte" style={{ fontSize: 15 }}>
          Le test porte sur {attendu} et après : des prix que le bot n’a jamais lus, ni pour apprendre, ni pour être choisi. Son champion les passe une seule fois, sans rien apprendre : il ne fait qu’essayer.
        </p>
        {benchmark === 'pret' ? (
          <div className="coffre-geste">
            <span className="second" style={{ fontSize: 13 }}>
              À côté de lui, le meilleur bot tiré au hasard à la génération 0, jamais entraîné, et l’achat conservé. Leurs trades sont ensuite rejoués dans le moteur exact. Le test ne s’ouvre qu’une fois.
            </span>
            <div className="champ">
              <span className="champ-nom">Pour l’ouvrir, tapez l’année du test : {attendu}</span>
              <CodeSlots length={4} value={code} onChange={setCode} status={statut} slotSize={46} ariaLabel="Année du test" disabled={!!tache || envoi} />
            </div>
            {/* Une commande refusee remet le bouton a zero : il est recree. */}
            <HoldButton key={erreur ?? 'pret'} disabled={statut !== 'success' || envoi || !!tache} onHold={lancer} holdTime={1600} resetAfter={0} doneLabel="Benchmark lancé" icon={<Icone nom="ouvert" taille={16} />} doneIcon={<Icone nom="coche" taille={16} />}>
              Maintenir pour ouvrir le test
            </HoldButton>
            {tache && <Message genre="alerte">Une tâche tourne déjà : la GPU ne sert qu’à une à la fois.</Message>}
            {erreur && <Message genre="critique">{erreur}</Message>}
          </div>
        ) : (
          <Message>{suite.texte}</Message>
        )}
      </div>
      {effets && (
        <div className="coffre-prisme" aria-hidden="true">
          <Prism animationType="hover" lightMode glow={0.8} noise={0} scale={3.2} hueShift={0} colorFrequency={1} bloom={0.9} timeScale={0.4} suspendWhenOffscreen />
        </div>
      )}
    </section>
  );
}

// Le benchmark tourne : sa sortie ici meme, et la seance des qu'il a fini.
function EnCours({ tache }) {
  const maintenant = useMaintenant();
  return (
    <Carte>
      <EnTeteCarte titre="Le benchmark tourne" description="Le champion et le bot tiré au hasard passent le bloc de test, trimestre par trimestre, puis leurs trades sont rejoués dans le moteur exact. La séance s’affiche ici dès la fin." actions={<Arret tache={tache} />} />
      <LatticeLoader label={tache.etat === 'arret demande' ? 'Arrêt demandé' : 'Sur le bloc de test'} elapsed={maintenant - Date.parse(tache.debut) / 1000} pattern="sweep" grid={4} cellSize={5} color={ACCENT} fontSize={14} />
      <Progression part={null} continu />
      <Journal tacheId={tache.id} hauteur={200} outils={false} />
    </Carte>
  );
}

function Resultats({ run, rapport }) {
  const differe = useDiffere();
  const effets = useEffetsActifs() && differe;
  const c = rapport.bots.champion;
  const bh = rapport.bots['buy and hold'];
  const hasard = rapport.bots['champion aleatoire'];
  const lignes = ORDRE.filter(b => rapport.bots[b]).map(b => [b, rapport.bots[b]]);
  const v = rapport.validation;
  return (
    <>
      <section className="verdict">
        {effets && (
          <div className="verdict-fond" aria-hidden="true">
            <PrismaticBurst colors={ECLAT} intensity={1.1} speed={0.25} animationType="rotate3d" distort={0.4} noise={0.2} lightMode />
          </div>
        )}
        <span className="oeil">Le verdict · sur des données jamais vues</span>
        <DepthText text={pctSigne(c.rendement_chaine)} fontSize="clamp(3.2rem, 7vw, 5.4rem)" fontWeight={760} layers={22} depth={1.6} tilt={6} depthColor={c.rendement_chaine >= 0 ? ACCENT : '#e34948'} orbitSpeed={0.18} />
        <p className="resume-texte">
          Votre bot a fait <strong>{pctSigne(c.rendement_chaine)}</strong>
          {bh ? (
            <>
              , quand acheter et garder faisait <strong>{pctSigne(bh.rendement_chaine)}</strong>
            </>
          ) : null}
          {hasard ? (
            <>
              {' '}
              et un bot tiré au hasard <strong>{pctSigne(hasard.rendement_chaine)}</strong>
            </>
          ) : null}
          . Sa pire baisse a été de {pct(c.drawdown_max, 1)}, en {nombre(c.trades)} trades dont {pct(c.taux_de_reussite, 0)} gagnants.
        </p>
        <span className="discret">
          Test ouvert le {quand(rapport.date)} · {rapport.trimestres.map(t => t.nom).join(', ')} · {nombre(rapport.trimestres.reduce((s, t) => s + t.barres, 0))} heures
        </span>
      </section>
      <Carte>
        <EnTeteCarte titre="Face à ses références" description="Le même bloc de test, pour chacun." />
        <div className="tableau-conteneur">
          <table className="tableau">
            <thead>
              <tr>
                <th className="gauche">Qui</th>
                <th>Rendement</th>
                <th>Pire baisse</th>
                <th>Trades</th>
                <th>Gagnants</th>
                <th>Sharpe</th>
                <th>Mieux que (bots au hasard)</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map(([b, m]) => (
                <tr key={b} className={b === 'champion' ? 'courante' : undefined}>
                  <td className="gauche">
                    <strong style={{ fontWeight: b === 'champion' ? 650 : 500 }}>{NOMS[b] ?? b}</strong>
                  </td>
                  <td>
                    <span className={m.rendement_chaine >= 0 ? 'signe-gain' : 'signe-perte'} />
                    {pctSigne(m.rendement_chaine)}
                  </td>
                  <td>{pct(m.drawdown_max, 1)}</td>
                  <td>{m.trades != null ? nombre(m.trades) : '–'}</td>
                  <td>{m.taux_de_reussite != null ? pct(m.taux_de_reussite, 0) : '–'}</td>
                  <td>{decimal(m.sharpe_annualise, 2)}</td>
                  <td>{m.rang_centile_reference != null ? pct(m.rang_centile_reference, 1) : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="discret">
          {rapport.conforme ? 'Rejeu exact conforme : le moteur retrouve les mêmes capitaux que la GPU.' : 'Rejeu exact NON conforme : le simulateur GPU est à corriger avant tout nouveau benchmark.'} En validation, sa note était de {decimal(v.note_champion, 4)} et son Deflated Sharpe Ratio de {decimal(v.deflated_sharpe_ratio, 3)}
          {v.ecart_au_hasard != null ? ` ; écart au hasard ${v.ecart_au_hasard > 0 ? '+' : ''}${decimal(v.ecart_au_hasard, 4)}` : ''}.
        </p>
      </Carte>
    </>
  );
}

export default function Benchmark({ run, detail }) {
  const { tache, taches } = useDonnees();
  const [rapport, setRapport] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [vue] = useState(() => dejaVue(run.nom));
  const [fini, setFini] = useState(vue);
  const { cotation } = paire(run.symbole);
  const config = detail?.config?.valeurs;
  useEffect(() => {
    if (!run.rapport) return;
    lire(`/api/runs/${enc(run.nom)}/rapport`)
      .then(setRapport)
      .catch(e => setErreur(e.message));
  }, [run.nom, run.rapport]);

  const enCours = tache?.type === 'benchmark' && tache.run === run.nom ? tache : null;
  const derniere = taches.find(t => t.type === 'benchmark' && t.run === run.nom);
  const echec = !enCours && !run.rapport && derniere && ECHECS.includes(derniere.etat) ? derniere : null;
  const rejeuxTest = detail?.rejeux?.benchmark ?? {};
  const rejeuxValidation = detail?.rejeux?.pantheon ?? {};
  const premier = Object.keys(rejeuxValidation).find(k => k.startsWith('1-'));
  const couts = {
    frais: Number(config?.frais_reference ?? 0.001),
    glissement: Number(config?.glissement_reference ?? 0.0005),
    decimalesPrix: String(config?.pas_de_prix ?? '0.01').split('.')[1]?.replace(/0+$/, '').length ?? 0
  };

  if (run.rapport) {
    const sansSeance = detail && !rejeuxTest.champion?.length;
    return (
      <>
        {erreur && <Message genre="critique">{erreur}</Message>}
        {rejeuxTest.champion?.length ? (
          <Seance
            nom={run.nom}
            trimestres={rejeuxTest.champion}
            hasard={rejeuxTest.champion_aleatoire?.length ? 'champion_aleatoire' : null}
            cotation={cotation}
            decimalesPrix={couts.decimalesPrix}
            autoplay={!vue}
            onFin={() => {
              marquerVue(run.nom);
              setFini(true);
            }}
          />
        ) : !detail ? (
          <Chargement texte="Lecture des trades" minHauteur={300} />
        ) : null}
        {(fini || sansSeance) && (rapport ? <Resultats run={run} rapport={rapport} /> : !erreur && <Chargement texte="Lecture du rapport" />)}
      </>
    );
  }

  return (
    <>
      {enCours ? (
        <EnCours tache={enCours} />
      ) : run.benchmark && derniere?.etat === 'terminee' ? (
        <Chargement texte="Le benchmark est fini : lecture de son rapport" />
      ) : run.benchmark ? (
        <Message genre="critique">Le dossier du benchmark existe sans rapport : il a été interrompu. Le bloc de test est considéré comme ouvert, et le bot refusera de le rouvrir.</Message>
      ) : (
        <Ouverture run={run} />
      )}
      {echec && (
        <Carte>
          <Message genre="critique">Le dernier benchmark s’est arrêté en erreur : sa sortie dit pourquoi.</Message>
          <Journal tacheId={echec.id} hauteur={200} outils={false} />
        </Carte>
      )}
      {!enCours &&
        !run.benchmark &&
        (premier ? (
          <Carte>
            <EnTeteCarte titre="En attendant : ses trades en validation" description={`Sur ${annee(run.debut_validation)}, l’année qui a servi à le choisir : ce n’est pas une preuve, mais on y voit comment il trade.`} />
            <Trades nom={run.nom} genre="pantheon" sous={premier} trimestres={rejeuxValidation[premier]} cotation={cotation} {...couts} />
          </Carte>
        ) : (
          <Carte>
            <Vide titre="Pas encore de trades à montrer">Son champion est rejoué dans le moteur exact à chaque arrêt de l’entraînement.</Vide>
          </Carte>
        ))}
    </>
  );
}
