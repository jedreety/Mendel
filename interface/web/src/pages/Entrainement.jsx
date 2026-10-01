// Entrainement : un choix simple (nouveau bot ou bot existant), puis son formulaire. Des qu'une tache tourne, la page
// devient la vue en direct de cette tache. A cote de la question, une helice de genomes tourne : la population.
import { useMemo } from 'react';
import { useDonnees, useEffetsActifs, useMaintenant } from '../donnees.jsx';
import { lien } from '../route.js';
import { ilya, nombre, note } from '../format.js';
import { listeBots, nomRun, useSuppressions } from '../bots.js';
import { Icone } from '../composants/Base.jsx';
import { Genome } from '../composants/Empreinte.jsx';
import InfiniteSpiral from '../reactbits/InfiniteSpiral/InfiniteSpiral.jsx';
import TiltedCard from '../reactbits/TiltedCard/TiltedCard.jsx';
import GlareHover from '../reactbits/GlareHover/GlareHover.jsx';
import Direct from './entrainement/Direct.jsx';
import Nouveau from './entrainement/Nouveau.jsx';
import Continuer from './entrainement/Continuer.jsx';

const ENTRAINEMENTS = ['nouveau', 'reprendre', 'a-blanc', 'hasard'];

// Le dernier entrainement, s'il vient de finir : ce qu'il a donne, et ou aller ensuite.
function DernierEntrainement() {
  const { taches, runs } = useDonnees();
  const maintenant = useMaintenant(10000);
  const t = taches.find(x => ENTRAINEMENTS.includes(x.type));
  if (!t?.fin_s || maintenant - t.fin_s > 3600) return null;
  const run = runs.find(r => r.nom === t.run);
  if (!run) return null;
  const bot = run.source ? runs.find(r => r.nom === run.source) ?? run : run;
  const fini = ['terminee', 'arretee'].includes(t.etat);
  return (
    <div className={`message ${fini ? 'bon' : 'alerte'}`}>
      <Icone nom={fini ? 'coche' : 'alerte'} />
      <div className="grille" style={{ gap: 6 }}>
        <span>
          <strong>« {nomRun(run, runs)} »</strong> {fini ? 's’est arrêté' : 's’est interrompu'} {ilya(t.fin_s, maintenant)}, à la génération {nombre(run.generation)}, avec une meilleure note de {note(run.meilleure_note)}.
        </span>
        <span className="ligne" style={{ gap: 14 }}>
          <a className="lien" href={lien(['bots', bot.nom])}>
            Voir le bot
          </a>
          {!fini && (
            <a className="lien" href="#/systeme/taches">
              Voir la sortie de la tâche
            </a>
          )}
        </span>
      </div>
    </div>
  );
}

function Helice() {
  const effets = useEffetsActifs();
  const genomes = useMemo(() => Array.from({ length: 26 }, (_, i) => ({ id: `g${i}`, contenu: <Genome graine={`bot-${i * 7 + 3}`} /> })), []);
  if (!effets) return <div />;
  return (
    <div className="helice" aria-hidden="true">
      <InfiniteSpiral items={genomes} speed={0.3} radius={110} cardWidth={54} cardHeight={54} verticalSpacing={20} cardsPerTurn={9} centerScale={1.1} edgeFade={0.3} edgeBlur={2} cardRadius={12} pauseOnHover={false} animationMode="auto" />
    </div>
  );
}

function CarteChoix({ href, icone, titre, texte, action, desactive }) {
  return (
    <TiltedCard>
      <GlareHover>
        <a className="carte-choix" href={href} aria-disabled={desactive || undefined}>
          <span className="icone-choix">
            <Icone nom={icone} taille={20} epaisseur={2} />
          </span>
          <strong>{titre}</strong>
          <span>{texte}</span>
          {action && (
            <span className="fleche-lien">
              {action}
              <Icone nom="fleche" taille={15} />
            </span>
          )}
        </a>
      </GlareHover>
    </TiltedCard>
  );
}

function Choix() {
  const { runs } = useDonnees();
  const supprimes = useSuppressions();
  const nb = listeBots(runs).filter(b => b.point_de_sauvegarde && !supprimes.has(b.nom)).length;
  return (
    <>
      <section className="heros heros-double">
        <div className="heros-contenu">
          <span className="oeil">Entraînement</span>
          <h1 className="bienvenue">Que voulez-vous entraîner ?</h1>
          <p className="resume-texte">Un bot apprend sur un seul marché, par générations successives. Partez de zéro avec une population neuve, ou continuez un bot là où il s’était arrêté.</p>
        </div>
        <Helice />
      </section>
      <DernierEntrainement />
      <div className="choix-grand">
        <CarteChoix href="#/entrainement/nouveau" icone="etincelle" titre="Nouveau bot" texte="Une nouvelle population, tirée au hasard. Vous choisissez son nom, son marché, ses années et sa durée." action="Commencer" />
        <CarteChoix
          href="#/entrainement/continuer"
          icone="rafraichir"
          titre="Continuer un bot"
          texte={nb ? `Reprendre l’entraînement d’un de vos ${nb} bot${nb > 1 ? 's' : ''}, une fois ou en boucle.` : 'Aucun bot à continuer pour l’instant.'}
          action={nb ? 'Choisir le bot' : null}
          desactive={!nb}
        />
      </div>
    </>
  );
}

export default function Entrainement({ page, params }) {
  const { tache } = useDonnees();
  if (tache) return <Direct tache={tache} />;
  if (page === 'nouveau') return <Nouveau params={params} />;
  if (page === 'continuer') return <Continuer params={params} />;
  return <Choix />;
}
