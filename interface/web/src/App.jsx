// Cadre de l'interface : panneau lateral a gauche (sections, barre de commande, tache en cours, connexion), page au
// centre sous le bandeau de sa section, flou progressif en haut et en bas de l'ecran, notifications. Quatre
// sections : Accueil, Entrainement, Bots, Systeme.
import { Component, lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { useDonnees, useMaintenant } from './donnees.jsx';
import { aller, lienTache, useRoute } from './route.js';
import { PAGES_SYSTEME, VUES_BOT, resoudre } from './navigation.js';
import { ICONES_TACHES, TYPES_TACHES } from './format.js';
import { listeBots, nomBot, nomRun, useSuppressions } from './bots.js';
import Icone from './composants/Icone.jsx';
import { Message } from './composants/Base.jsx';
import Bandeau from './composants/Bandeau.jsx';
import Chargement from './composants/Chargement.jsx';
import { CommandeFlottante, ouvrirCommande } from './composants/Commande.jsx';
import { Toasts, useEvenements } from './composants/Notifications.jsx';
import BranchedMenu from './reactbits/BranchedMenu/BranchedMenu.jsx';
import CallChip from './reactbits/CallChip/CallChip.jsx';
import GradualBlur from './reactbits/GradualBlur/GradualBlur.jsx';
import Accueil from './pages/Accueil.jsx';

// Pages chargees a la demande : l'accueil s'affiche sans attendre les graphiques. Elles sont ensuite prechargees
// pendant un temps mort, pour que la navigation n'attende jamais.
const charger = {
  entrainement: () => import('./pages/Entrainement.jsx'),
  bots: () => import('./pages/Bots.jsx'),
  bot: () => import('./pages/Bot.jsx'),
  systeme: () => import('./pages/Systeme.jsx')
};
const Entrainement = lazy(charger.entrainement);
const Bots = lazy(charger.bots);
const Bot = lazy(charger.bot);
const Systeme = lazy(charger.systeme);

const BOTS_AU_MENU = 5;
const SORTIE = [0.23, 1, 0.32, 1];

// Une erreur dans une page n'emporte qu'elle : le panneau lateral et les autres pages restent utilisables.
class Garde extends Component {
  state = { erreur: null };
  static getDerivedStateFromError(erreur) {
    return { erreur };
  }
  render() {
    if (!this.state.erreur) return this.props.children;
    return <Message genre="critique">Cette page a rencontré une erreur : {String(this.state.erreur?.message ?? this.state.erreur)}. Les autres pages restent utilisables ; F5 la recharge.</Message>;
  }
}

// La tache en cours, ou la derniere pendant dix minutes apres sa fin.
function TacheDuPanneau() {
  const { tache, taches, runs, decalage, connecte } = useDonnees();
  const maintenant = useMaintenant(5000);
  const derniere = tache ?? taches[0];
  const recente = derniere && (tache || (derniere.fin_s && maintenant - derniere.fin_s < 600));
  if (!recente) {
    return (
      <div className="barre-etat">
        <span className={`point ${connecte ? '' : 'critique'}`} />
        <span>{connecte ? 'GPU libre, aucune tâche' : 'Serveur injoignable : reconnexion…'}</span>
      </div>
    );
  }
  const run = runs.find(r => r.nom === (derniere.source ?? derniere.run));
  const quoi = run ? nomRun(run, runs) : derniere.nom || derniere.symbole || '';
  const debut = Date.parse(derniere.debut) - decalage;
  const statut = tache ? 'running' : ['echec', 'tuee', 'interrompue'].includes(derniere.etat) ? 'error' : 'done';
  const duree = tache ? undefined : (derniere.fin_s - Date.parse(derniere.debut) / 1000) * 1000;
  return (
    <>
      <a href={tache ? lienTache(tache) : '#/systeme/taches'} title={tache ? 'Suivre en direct' : 'Voir les tâches'} style={{ textDecoration: 'none' }}>
        <CallChip icon={ICONES_TACHES[derniere.type] ?? 'eclair'} name={quoi || TYPES_TACHES[derniere.type]} status={statut} depuis={debut} dureeMs={duree} size={36} />
      </a>
      <div className="barre-etat">
        <span className={`point ${connecte ? (tache ? 'vivant' : '') : 'critique'}`} />
        <span>{!connecte ? 'Serveur injoignable : reconnexion…' : tache ? (tache.etat === 'arret demande' ? 'Arrêt demandé' : `${TYPES_TACHES[tache.type] ?? 'Tâche'} en cours`) : `${TYPES_TACHES[derniere.type] ?? 'Tâche'} fini${statut === 'error' ? ' en erreur' : ''}`}</span>
      </div>
    </>
  );
}

function Barre({ route }) {
  const { runs, tache } = useDonnees();
  const supprimes = useSuppressions();
  const bots = useMemo(() => listeBots(runs).filter(b => !supprimes.has(b.nom)).slice(0, BOTS_AU_MENU), [runs, supprimes]);
  const enDirect = !!tache;
  const items = useMemo(
    () => [
      { value: 'accueil', label: 'Accueil', icon: <Icone nom="maison" taille={17} /> },
      { value: 'entrainement', label: 'Entraînement', icon: <Icone nom="eclair" taille={17} />, extra: enDirect ? <span className="point vivant" style={{ marginLeft: 'auto', marginRight: 6 }} /> : null },
      {
        label: 'Bots',
        icon: <Icone nom="bot" taille={17} />,
        children: [{ value: 'bots', label: 'Tous les bots' }, ...bots.map(b => ({ value: `bots/${b.nom}`, label: nomBot(b), title: nomBot(b) }))]
      },
      { label: 'Système', icon: <Icone nom="systeme" taille={17} />, children: PAGES_SYSTEME.map(p => ({ value: `systeme/${p.cle}`, label: p.libelle })) }
    ],
    [bots, enDirect]
  );
  const actif =
    route.section === 'bots'
      ? route.bot && bots.some(b => b.nom === route.bot)
        ? `bots/${route.bot}`
        : 'bots'
      : route.section === 'systeme'
        ? `systeme/${route.page}`
        : route.section;
  const choisir = valeur => {
    if (valeur === 'accueil') aller([]);
    else if (valeur.startsWith('bots/')) aller(['bots', valeur.slice(5)]);
    else aller(valeur.split('/'));
  };
  return (
    <aside className="barre">
      <a className="marque" href="#/">
        <span className="marque-logo">
          <Icone nom="graphique" taille={18} epaisseur={2.2} />
        </span>
        <span>
          <strong>Mendel</strong>
          <small>entraînement sur GPU</small>
        </span>
      </a>
      <button type="button" className="barre-recherche" onClick={() => ouvrirCommande(true)}>
        <Icone nom="recherche" taille={15} />
        Aller à…
        <kbd>Ctrl K</kbd>
      </button>
      <BranchedMenu items={items} active={actif} onSelect={choisir} defaultOpen={[2]} width={212} />
      <div className="barre-bas">
        <TacheDuPanneau />
      </div>
    </aside>
  );
}

function titre(route, runs) {
  if (route.section === 'bots' && route.bot) {
    const run = runs.find(r => r.nom === route.bot);
    return [run ? nomRun(run, runs) : route.bot, VUES_BOT.find(v => v.cle === route.vue)?.libelle];
  }
  if (route.section === 'systeme') return [PAGES_SYSTEME.find(p => p.cle === route.page)?.libelle, 'Système'];
  return [{ accueil: 'Accueil', entrainement: 'Entraînement', bots: 'Bots' }[route.section]];
}

// Le fond du bandeau de chaque section. Pendant une tache, la vue en direct reste calme : la GPU est au bot.
function fondDe(route, tache) {
  if (route.section === 'accueil') return 'aurore';
  if (route.section === 'entrainement') return tache ? 'calme' : route.page === 'nouveau' ? 'courbes' : route.page === 'continuer' ? 'laser' : 'rayons';
  if (route.section === 'bots') return route.bot ? 'calme' : 'stores';
  if (route.section === 'systeme') return 'lumiere';
  return 'calme';
}

// Vrai des que la page a defile : le flou du haut n'apparait qu'alors.
function useDefile() {
  const [defile, setDefile] = useState(false);
  useEffect(() => {
    const suivre = () => setDefile(window.scrollY > 8);
    suivre();
    window.addEventListener('scroll', suivre, { passive: true });
    return () => window.removeEventListener('scroll', suivre);
  }, []);
  return defile;
}

export default function App() {
  const { parties, params } = useRoute();
  const route = resoudre(parties);
  const { runs, tache } = useDonnees();
  const reduit = useReducedMotion();
  const defile = useDefile();
  useEvenements();

  useEffect(() => {
    if (route.redirection) aller(route.redirection, params);
  }, [route.redirection]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.section, route.page, route.bot]);
  useEffect(() => {
    document.title = [...titre(route, runs), 'Mendel'].filter(Boolean).join(' · ');
  });
  useEffect(() => {
    const precharger = () => Object.values(charger).forEach(f => f().catch(() => {}));
    if ('requestIdleCallback' in window) {
      const id = requestIdleCallback(precharger, { timeout: 3000 });
      return () => cancelIdleCallback(id);
    }
    const id = setTimeout(precharger, 1500);
    return () => clearTimeout(id);
  }, []);

  if (route.redirection) return null;
  const cle = route.section === 'bots' ? `bots-${route.bot ?? ''}` : `${route.section}-${route.page ?? ''}`;
  let page;
  if (route.section === 'entrainement') page = <Entrainement page={route.page} params={params} />;
  else if (route.section === 'bots') page = route.bot ? <Bot nom={route.bot} vue={route.vue} params={params} /> : <Bots />;
  else if (route.section === 'systeme') page = <Systeme page={route.page} params={params} />;
  else page = <Accueil />;

  return (
    <div className="cadre">
      <Barre route={route} />
      <main className="principal">
        <Bandeau fond={fondDe(route, tache)} />
        <Suspense fallback={<Chargement texte="Chargement" minHauteur={360} />}>
          <motion.div key={cle} className="page" initial={reduit ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.38, ease: SORTIE }}>
            <Garde key={cle}>{page}</Garde>
          </motion.div>
        </Suspense>
      </main>
      <div className="flou-haut" data-visible={defile ? '' : undefined} aria-hidden="true">
        <GradualBlur position="top" height="100%" strength={1.4} divCount={4} curve="bezier" exponential opacity={1} zIndex={1} />
      </div>
      <div className="flou-bas" aria-hidden="true">
        <GradualBlur position="bottom" height="100%" strength={2.2} divCount={6} curve="bezier" exponential opacity={1} zIndex={1} />
      </div>
      <CommandeFlottante />
      <Toasts />
    </div>
  );
}
