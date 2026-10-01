// Continuer un bot : son entrainement reprend exactement la ou il s'etait arrete (meme population, meme
// Pantheon), pour un nombre fixe de generations de plus, ou en boucle.
import { useState } from 'react';
import { envoyer } from '../../api.js';
import { useDonnees } from '../../donnees.jsx';
import { duree, nombre, note } from '../../format.js';
import { estimer } from '../../estimation.js';
import { libellePaire, listeBots, nomBot, periode, useSuppressions } from '../../bots.js';
import { Carte, Chiffre, EnTete, EnTeteCarte, Message, Segments, Vide } from '../../composants/Base.jsx';
import GlideSelect from '../../reactbits/GlideSelect/GlideSelect.jsx';
import JellyRadio from '../../reactbits/JellyRadio/JellyRadio.jsx';
import SlideCommit from '../../reactbits/SlideCommit/SlideCommit.jsx';

const PRESETS = [10, 25, 50, 100, 200];

function pourquoiArrete(b) {
  if (b.generations_max != null && b.generation >= b.generations_max) return `Il avait fait les ${nombre(b.generations_max)} générations prévues.`;
  if (b.stagnation_max && b.stagnation != null && b.stagnation >= b.stagnation_max) return `Il s’était arrêté faute de progrès depuis ${b.stagnation} générations.`;
  return 'Il avait été arrêté en cours de route.';
}

export default function Continuer({ params }) {
  const { runs, tache, rafraichir } = useDonnees();
  const supprimes = useSuppressions();
  const bots = listeBots(runs).filter(b => b.point_de_sauvegarde && !supprimes.has(b.nom));
  // Le choix se deduit a chaque rendu : la liste des bots peut arriver apres l'ouverture de la page.
  const [selection, setChoisi] = useState(params.bot ?? '');
  const choisi = [selection, params.bot].find(n => n && bots.some(b => b.nom === n)) ?? bots[0]?.nom ?? '';
  const [mode, setMode] = useState('fois');
  const [n, setN] = useState(50);
  const [erreur, setErreur] = useState(null);
  const bot = bots.find(b => b.nom === choisi);

  if (!bots.length) {
    return (
      <>
        <EnTete retour="#/entrainement" surtitre={<span className="oeil">Entraînement</span>} titre="Continuer un bot" />
        <Carte>
          <Vide titre="Aucun bot à continuer">
            Un bot se continue dès qu’il a un point de sauvegarde, c’est-à-dire après sa première génération.
            <a className="bouton primaire" href="#/entrainement/nouveau">
              Créer un bot
            </a>
          </Vide>
        </Carte>
      </>
    );
  }

  const valide = mode === 'boucle' || (Number.isInteger(n) && n >= 1 && n <= 100000);
  const estimation = bot ? estimer(runs, bot.population ?? 0, mode === 'boucle' ? null : n) : null;

  const lancer = async () => {
    setErreur(null);
    try {
      await envoyer('/api/taches', { type: 'reprendre', run: choisi, ...(mode === 'boucle' ? { boucle: true } : { generations: n }) });
      rafraichir();
    } catch (e) {
      setErreur(e.message);
      throw e;
    }
  };

  return (
    <>
      <EnTete retour="#/entrainement" surtitre={<span className="oeil">Entraînement</span>} titre="Continuer un bot" description="Il reprend exactement là où il s’était arrêté : même population, même Panthéon, mêmes graines." />
      <Carte>
        <div className="etape">
          <span className="etape-numero">1</span>
          <div className="etape-contenu">
            <span className="champ-nom">Quel bot</span>
            <GlideSelect size="lg" menuWidth={320} value={choisi} ariaLabel="Bot à continuer" onChange={setChoisi} options={bots.map(b => ({ value: b.nom, label: nomBot(b), tag: `${libellePaire(b.symbole)} · gén. ${b.generation}` }))} />
            {bot && (
              <>
                <div className="chiffres">
                  <Chiffre libelle="Générations" valeur={nombre(bot.generation)} detail={periode(bot) ? `sur ${libellePaire(bot.symbole)}, ${periode(bot)}` : null} />
                  <Chiffre libelle="Meilleure note" aide="noteValidation" valeur={note(bot.meilleure_note)} detail={bot.generation_meilleure != null ? `trouvée à la génération ${bot.generation_meilleure}` : null} />
                  <Chiffre libelle="Déjà entraîné" valeur={duree(bot.duree_totale_s)} detail="temps de calcul cumulé" />
                </div>
                <p className="second">{pourquoiArrete(bot)}</p>
                {bot.actif && <Message genre="alerte">Ce bot a été écrit il y a moins de cinq minutes : attendez qu’il soit à l’arrêt.</Message>}
                {bot.benchmark && <Message genre="alerte">Son benchmark a déjà été fait : même si son champion change, son bloc de test ne se rouvrira pas.</Message>}
              </>
            )}
          </div>
        </div>
        <div className="etape">
          <span className="etape-numero">2</span>
          <div className="etape-contenu">
            <span className="champ-nom">Combien de temps</span>
            <div className="ligne" style={{ gap: 14 }}>
              <Segments
                etiquette="Durée de l’entraînement"
                actif={mode}
                onChange={setMode}
                elements={[
                  { cle: 'fois', libelle: 'Une seule fois', icone: 'cible' },
                  { cle: 'boucle', libelle: 'En boucle', icone: 'boucle' }
                ]}
              />
              <span className="second">{mode === 'boucle' ? 'Il tourne jusqu’à ce que vous l’arrêtiez.' : 'Exactement ce nombre de générations de plus, puis il s’arrête.'}</span>
            </div>
            {mode === 'fois' && (
              <div className="ligne" style={{ gap: 12 }}>
                <input className="saisie" style={{ width: 104 }} type="number" min={1} max={100000} value={n} onChange={e => setN(Math.round(Number(e.target.value)))} aria-label="Générations de plus" />
                <span className="second">générations de plus</span>
                <JellyRadio swell={0.14} className="rangee-jelly" size="sm" ariaLabel="Générations prédéfinies" items={PRESETS.map(x => ({ value: x, label: String(x) }))} value={PRESETS.includes(n) ? n : null} onChange={setN} />
              </div>
            )}
            {estimation && <p className="discret">{mode === 'boucle' ? `Environ ${duree(estimation.parGeneration)} par génération.` : `Environ ${duree(estimation.total)} en tout, jusqu’à la génération ${nombre((bot?.generation ?? 0) + n)}.`}</p>}
          </div>
        </div>
      </Carte>
      <Carte>
        <EnTeteCarte titre="C’est parti ?" description="L’arrêt se demande à tout moment depuis la vue en direct : le bot finit sa génération et sauvegarde." />
        {tache && <Message genre="alerte">Une tâche tourne déjà : la GPU ne sert qu’à une à la fois.</Message>}
        {erreur && <Message genre="critique">{erreur}</Message>}
        <SlideCommit label="Glisser pour continuer l’entraînement" doneLabel="Lancé" errorLabel="Refusé" width={360} height={54} disabled={!bot || bot.actif || !valide || !!tache} onConfirm={lancer} />
      </Carte>
    </>
  );
}
