// Nouveau bot : un nom, un marche, des annees et une duree. Tout le reste est dans les parametres avances.
// Chaque choix ecrit dans la configuration du bot (evolution/config.toml), relue par son propre lecteur avant
// tout lancement : le formulaire n'invente aucune regle que le bot n'applique pas deja.
import { useEffect, useMemo, useState } from 'react';
import { enc, envoyer, lire } from '../../api.js';
import { useDonnees, useMarches } from '../../donnees.jsx';
import { argent, duree, nombre, pct } from '../../format.js';
import { estimer } from '../../estimation.js';
import { annee, libellePaire, listeBots, nomBot, paire } from '../../bots.js';
import { Carte, EnTete, EnTeteCarte, Icone, Message, Segments, Vide } from '../../composants/Base.jsx';
import { Terme } from '../../composants/Aide.jsx';
import Chargement from '../../composants/Chargement.jsx';
import GlideSelect from '../../reactbits/GlideSelect/GlideSelect.jsx';
import JellyRadio from '../../reactbits/JellyRadio/JellyRadio.jsx';
import SlideCommit from '../../reactbits/SlideCommit/SlideCommit.jsx';
import StatusMark from '../../reactbits/StatusMark/StatusMark.jsx';
import EditeurConfig, { LIBELLES, appliquer, valeurDe } from './Config.jsx';

const DECIMAL = /^\d+(\.\d+)?$/;
const PRESETS = [10, 25, 50, 100, 200];
const LIEU = ['pas_de_prix', 'pas_de_quantite', 'notionnel_minimum'];
const JOUR = 86400000;
const intervalle = (a, b) => (a <= b ? Array.from({ length: b - a + 1 }, (_, i) => a + i) : []);

// Annees d'un marche : il faut de l'historique avant l'entrainement (indicateurs et run a blanc), puis une
// annee de validation et au moins une annee de test apres lui.
function bornes(m) {
  const premiere = annee(m?.premiere);
  const derniere = annee(m?.derniere);
  return { premiere, derniere, debuts: intervalle(premiere + 1, derniere - 3), fins: intervalle(premiere + 2, derniere - 2) };
}

function avecAnnees(config, a, b) {
  let c = appliquer(config, 'debut_entrainement', `${a}-01-01`);
  c = appliquer(c, 'debut_validation', `${b + 1}-01-01`);
  return appliquer(c, 'debut_test', `${b + 2}-01-01`);
}

function Annees({ premiere, derniere, aEnt, aVal, aTest }) {
  const annees = intervalle(premiere, derniere);
  const role = y => (y < aEnt ? ['historique', 'chauffe'] : y < aVal ? ['entrainement', 'apprend'] : y < aTest ? ['validation', 'choisit'] : ['test', 'jamais vu']);
  return (
    <div className="annees" style={{ '--n': annees.length }}>
      {annees.map(y => {
        const [classe, libelle] = role(y);
        return (
          <div key={y} className={`annee ${classe}`} title={{ historique: 'Sert à chauffer les indicateurs', entrainement: 'Le bot apprend ici', validation: 'Sert à choisir les meilleurs bots', test: 'Réservé au benchmark, jamais lu pendant l’entraînement' }[classe]}>
            {y}
            <small>{libelle}</small>
          </div>
        );
      })}
    </div>
  );
}

export default function Nouveau({ params = {} }) {
  const { runs, tache, rafraichir } = useDonnees();
  const marches = useMarches();
  const [base, setBase] = useState(null);
  const [config, setConfig] = useState(null);
  const [verification, setVerification] = useState(null);
  const [nom, setNom] = useState('');
  const [nomTouche, setNomTouche] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [nFois, setNFois] = useState(50);

  // Configuration du bot, avec « une seule fois, 50 generations » par defaut ; ou celle d'un bot (?depuis=).
  useEffect(() => {
    lire('/api/config')
      .then(async c => {
        const b = { texte: c.texte, champs: c.champs };
        setBase(b);
        if (params.depuis) {
          const d = await lire(`/api/config?depuis=${enc(params.depuis)}`).catch(() => null);
          if (d) {
            setConfig({ texte: d.texte, champs: d.champs });
            const g = Number(d.champs.find(x => x.cle === 'generations_max')?.valeur) || 0;
            if (g) setNFois(g);
            return;
          }
        }
        setConfig(appliquer(b, 'generations_max', 50));
      })
      .catch(e => setErreur(e.message));
  }, [params.depuis]);

  const v = cle => valeurDe(config, cle);
  const donnees = v('donnees');
  const marche = marches?.find(m => m.donnees === donnees);
  const symbole = marche?.symbole ?? String(donnees ?? '').split('/').pop().split('-')[0];
  const { base: actif, cotation } = paire(symbole);
  const { premiere, derniere, debuts, fins } = bornes(marche);
  const aEnt = annee(v('debut_entrainement'));
  const aVal = annee(v('debut_validation'));
  const aTest = annee(v('debut_test'));
  const generationsMax = Number(v('generations_max')) || 0;
  const boucle = generationsMax === 0;
  const suggestion = actif && aEnt && aVal ? `${actif} ${aEnt}${aVal - 1 > aEnt ? `–${aVal - 1}` : ''}` : '';

  useEffect(() => {
    if (!nomTouche) setNom(suggestion);
  }, [suggestion, nomTouche]);

  // Ce que le formulaire verifie lui-meme, avant de demander au bot.
  const problemes = useMemo(() => {
    if (!config || !marche) return [];
    const p = [];
    if (!nom.trim()) p.push('Donnez un nom au bot.');
    for (const cle of LIEU) {
      const x = String(v(cle) ?? '');
      if (!DECIMAL.test(x) || Number(x) <= 0) p.push(`${LIBELLES[cle]} : indiquez un nombre positif (fiche du marché chez Binance).`);
    }
    if (aEnt < premiere + 1) p.push(`L’entraînement doit commencer après ${premiere} : les indicateurs ont besoin d’historique.`);
    if (aTest > derniere) p.push(`Le test commencerait en ${aTest}, après la fin des données (${derniere}).`);
    const joursEnt = (Date.parse(v('debut_validation')) - Number(v('prechauffage_jours')) * JOUR - Date.parse(v('debut_entrainement'))) / JOUR;
    const requis = (Number(v('fenetres_par_lot')) + 1) * Number(v('duree_fenetre_jours'));
    if (joursEnt < requis) p.push(`Il faut au moins ${nombre(requis)} jours d’entraînement pour tirer ${v('fenetres_par_lot')} fenêtres de ${v('duree_fenetre_jours')} jours : élargissez les années.`);
    if (!boucle && generationsMax < 1) p.push('Indiquez un nombre de générations.');
    return p;
  }, [config, marche, nom, aEnt, aTest, premiere, derniere, boucle, generationsMax]); // eslint-disable-line react-hooks/exhaustive-deps

  // Relecture par le lecteur du bot, un instant apres la derniere modification.
  useEffect(() => {
    if (!config || problemes.length || verification?.texte === config.texte) return;
    const texte = config.texte;
    const minuterie = setTimeout(() => {
      envoyer('/api/config/verifier', { texte })
        .then(r => setVerification({ ...r, texte }))
        .catch(e => setVerification({ ok: false, erreur: e.message, texte }));
    }, 500);
    return () => clearTimeout(minuterie);
  }, [config, problemes, verification]);

  const changerMarche = async chemin => {
    const m = marches.find(x => x.donnees === chemin);
    let lieu = null;
    if (chemin === valeurDe(base, 'donnees')) lieu = Object.fromEntries(LIEU.map(k => [k, valeurDe(base, k)]));
    const bot = !lieu && listeBots(runs).find(r => r.donnees === chemin);
    if (bot) {
      try {
        const c = await lire(`/api/config?depuis=${enc(bot.nom)}`);
        const valeurs = Object.fromEntries(c.champs.map(x => [x.cle, x.valeur]));
        lieu = Object.fromEntries(LIEU.map(k => [k, valeurs[k]]));
      } catch {
        /* on repart des valeurs deduites du fichier */
      }
    }
    // Sans bot sur ce marche : le pas de prix le plus grossier que le fichier admet, le pas de quantite a saisir.
    lieu ??= { pas_de_prix: m.decimales_prix ? `0.${'0'.repeat(m.decimales_prix - 1)}1` : '1', pas_de_quantite: '', notionnel_minimum: valeurDe(base, 'notionnel_minimum') };
    const b = bornes(m);
    setConfig(c0 => {
      let c = appliquer(c0, 'donnees', chemin);
      for (const cle of LIEU) c = appliquer(c, cle, lieu[cle]);
      const a = annee(valeurDe(c, 'debut_entrainement'));
      const f = annee(valeurDe(c, 'debut_validation')) - 1;
      if (!b.debuts.includes(a) || !b.fins.includes(f) || f < a + 1) {
        const fin = b.fins[b.fins.length - 1];
        c = avecAnnees(c, Math.max(b.premiere + 1, fin - 3), fin);
      }
      return c;
    });
  };

  const choisirMode = mode => {
    let c = appliquer(config, 'generations_max', mode === 'boucle' ? 0 : nFois);
    c = appliquer(c, 'stagnation_max', mode === 'boucle' ? 0 : valeurDe(base, 'stagnation_max'));
    setConfig(c);
  };
  const choisirN = n => {
    setNFois(n);
    if (Number.isInteger(n) && n > 0) setConfig(appliquer(config, 'generations_max', n));
  };

  const partirDe = async run => {
    try {
      const c = await lire(`/api/config?depuis=${enc(run)}`);
      setConfig({ texte: c.texte, champs: c.champs });
      const g = Number(c.champs.find(x => x.cle === 'generations_max')?.valeur) || 0;
      if (g) setNFois(g);
    } catch (e) {
      setErreur(e.message);
    }
  };

  const lancer = async () => {
    setErreur(null);
    try {
      await envoyer('/api/taches', { type: 'nouveau', config: config.texte, nom: nom.trim() });
      rafraichir();
    } catch (e) {
      setErreur(e.message);
      throw e;
    }
  };

  if (erreur && !config) return <Message genre="critique">{erreur}</Message>;
  if (!config || !marches) return <Chargement texte="Lecture de la configuration" minHauteur={320} />;
  if (!marches.length) {
    return (
      <Carte>
        <Vide titre="Aucun marché disponible">
          Il faut d’abord des barres horaires dans data/prepared/.
          <a className="bouton primaire" href="#/systeme/donnees">
            Télécharger un marché
          </a>
        </Vide>
      </Carte>
    );
  }

  const verifie = verification?.texte === config.texte;
  const pret = !problemes.length && verifie && verification.ok && !tache;
  const population = Number(v('population')) || 0;
  const estimation = estimer(runs, population, boucle ? null : generationsMax);
  const stagnation = Number(v('stagnation_max')) || 0;
  const dejaTestes = listeBots(runs).filter(r => r.benchmark && r.donnees === donnees && annee(r.debut_test) <= derniere && annee(r.debut_test) < aTest);
  const [fraisMin, fraisMax] = v('frais_entrainement') ?? [];

  return (
    <>
      <EnTete retour="#/entrainement" surtitre={<span className="oeil">Entraînement</span>} titre="Nouveau bot" description="Une population neuve de bots tirés au hasard, qui évolue sur un seul marché. Quatre choix suffisent ; le reste a des valeurs par défaut." />
      <Carte>
        <div className="etape">
          <span className="etape-numero">1</span>
          <div className="etape-contenu">
            <div className="champ">
              <span className="champ-nom">Son nom</span>
              <input
                className="saisie grande"
                value={nom}
                maxLength={60}
                placeholder="Par exemple : Bitcoin 2020–2023"
                onChange={e => {
                  setNom(e.target.value);
                  setNomTouche(true);
                }}
              />
              <span className="champ-aide">Il se change à tout moment depuis la page du bot.</span>
            </div>
          </div>
        </div>
        <div className="etape">
          <span className="etape-numero">2</span>
          <div className="etape-contenu">
            <div className="champ">
              <span className="champ-nom">Son marché</span>
              <div className="ligne">
                <GlideSelect
                  size="lg"
                  menuWidth={280}
                  value={donnees}
                  ariaLabel="Marché"
                  onChange={changerMarche}
                  options={marches.map(m => ({ value: m.donnees, label: libellePaire(m.symbole), tag: `${annee(m.premiere)} → ${annee(m.derniere)}` }))}
                />
                <a className="lien" href="#/systeme/donnees" style={{ fontSize: 13 }}>
                  Ajouter un marché
                </a>
              </div>
              <span className="champ-aide">Un bot ne connaît qu’un marché : il y apprend, il y est testé.</span>
            </div>
            {marche && donnees !== valeurDe(base, 'donnees') && (
              <div className="grille" style={{ gap: 10 }}>
                <Message genre="alerte">
                  Pour {libellePaire(symbole)}, le bot doit connaître les règles du marché chez Binance : elles sont sur la fiche du marché (filtres PRICE_FILTER, LOT_SIZE et NOTIONAL). Le pas de prix est déduit des données ; vérifiez-le.
                </Message>
                <div className="champs">
                  {LIEU.map(cle => (
                    <label key={cle} className="champ">
                      <span className="champ-nom">{LIBELLES[cle]}</span>
                      <input className={`saisie ${DECIMAL.test(String(v(cle) ?? '')) && Number(v(cle)) > 0 ? '' : 'invalide'}`} value={v(cle) ?? ''} inputMode="decimal" onChange={e => setConfig(appliquer(config, cle, e.target.value.trim()))} placeholder={cle === 'pas_de_quantite' ? `en ${actif}` : ''} />
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="etape">
          <span className="etape-numero">3</span>
          <div className="etape-contenu">
            <div className="champ">
              <span className="champ-nom">Ses années</span>
              <div className="ligne">
                <span className="second">Il apprend de</span>
                <GlideSelect value={aEnt} ariaLabel="Première année d’entraînement" menuWidth={120} onChange={a => setConfig(avecAnnees(config, a, Math.max(a + 1, aVal - 1)))} options={debuts.map(y => ({ value: y, label: String(y) }))} />
                <span className="second">à</span>
                <GlideSelect value={aVal - 1} ariaLabel="Dernière année d’entraînement" menuWidth={120} onChange={b => setConfig(avecAnnees(config, aEnt, b))} options={fins.filter(y => y > aEnt).map(y => ({ value: y, label: String(y) }))} />
              </div>
              <span className="second">
                Puis il se valide sur {aTest - aVal > 1 ? `${aVal} à ${aTest - 1}` : aVal}, et garde {aTest < derniere ? `${aTest} à ${derniere}` : aTest} pour son <Terme id="benchmark">benchmark</Terme>, des données qu’il ne verra jamais avant.
              </span>
            </div>
            {premiere && <Annees premiere={premiere} derniere={derniere} aEnt={aEnt} aVal={aVal} aTest={aTest} />}
            {dejaTestes.length > 0 && (
              <p className="discret">
                À savoir : {dejaTestes.map(b => `« ${nomBot(b)} »`).join(', ')} {dejaTestes.length > 1 ? 'ont' : 'a'} déjà été testé{dejaTestes.length > 1 ? 's' : ''} sur une partie de ces années. Vous avez vu ces résultats : un réglage choisi après coup n’est plus tout à fait neutre.
              </p>
            )}
          </div>
        </div>
        <div className="etape">
          <span className="etape-numero">4</span>
          <div className="etape-contenu">
            <span className="champ-nom">Combien de temps</span>
            <div className="ligne" style={{ gap: 14 }}>
              <Segments
                etiquette="Durée de l’entraînement"
                actif={boucle ? 'boucle' : 'fois'}
                onChange={choisirMode}
                elements={[
                  { cle: 'fois', libelle: 'Une seule fois', icone: 'cible' },
                  { cle: 'boucle', libelle: 'En boucle', icone: 'boucle' }
                ]}
              />
              <span className="second">{boucle ? 'Il tourne jusqu’à ce que vous l’arrêtiez. Chaque génération est sauvegardée.' : 'Un nombre fixe de générations, puis il s’arrête et rejoue son Panthéon.'}</span>
            </div>
            {!boucle && (
              <div className="ligne" style={{ gap: 12 }}>
                <input className="saisie" style={{ width: 104 }} type="number" min={1} max={100000} value={nFois} onChange={e => choisirN(Math.round(Number(e.target.value)))} aria-label="Nombre de générations" />
                <span className="second">générations</span>
                <JellyRadio swell={0.14} className="rangee-jelly" size="sm" ariaLabel="Générations prédéfinies" items={PRESETS.map(n => ({ value: n, label: String(n) }))} value={PRESETS.includes(generationsMax) ? generationsMax : null} onChange={choisirN} />
              </div>
            )}
            <p className="discret">
              {boucle
                ? `Environ ${duree(estimation.parGeneration)} par génération de ${nombre(population)} bots, après ${duree(estimation.demarrage)} de démarrage.`
                : `Environ ${duree(estimation.total)} en tout, ${duree(estimation.parGeneration)} par génération de ${nombre(population)} bots.`}
              {!boucle && stagnation && generationsMax > stagnation ? ` Il s’arrête plus tôt si sa note ne progresse plus pendant ${stagnation} générations.` : ''}
            </p>
          </div>
        </div>
      </Carte>

      <details className="avances">
        <summary>
          <Icone nom="reglages" />
          Paramètres avancés
          <span className="discret" style={{ fontWeight: 400 }}>
            population, notation, coûts, réseau…
          </span>
        </summary>
        <div className="avances-contenu">
          <div className="ligne">
            <span className="second">Partir de la configuration d’un bot :</span>
            <GlideSelect placeholder="Choisir un bot" menuWidth={260} onChange={partirDe} options={listeBots(runs).map(b => ({ value: b.nom, label: nomBot(b), tag: libellePaire(b.symbole) }))} />
          </div>
          <EditeurConfig config={config} setConfig={setConfig} defaut={base.champs} exclure={['donnees']} />
        </div>
      </details>

      <Carte className="carte-lancement">
        <EnTeteCarte titre="Récapitulatif" description="Relisez, puis glissez pour lancer. L’arrêt se demande à tout moment depuis la vue en direct." />
        <dl className="cles-valeurs">
          <dt>Bot</dt>
          <dd>
            <strong>{nom.trim() || '–'}</strong>, sur {libellePaire(symbole)}
          </dd>
          <dt>Années</dt>
          <dd>
            apprend {aEnt}
            {aVal - 1 > aEnt ? `–${aVal - 1}` : ''}, validation {aVal}
            {aTest - aVal > 1 ? `–${aTest - 1}` : ''}, test {aTest}
            {derniere > aTest ? `–${derniere}` : ''}
          </dd>
          <dt>Durée</dt>
          <dd>{boucle ? 'en boucle, jusqu’à l’arrêt' : `${nombre(generationsMax)} générations`}</dd>
          <dt>Argent</dt>
          <dd>
            chaque bot démarre chaque période avec {argent(v('capital_initial'), cotation)} fictifs ; frais {fraisMin != null ? `${pct(Number(fraisMin), 2)} à ${pct(Number(fraisMax), 2)}` : '–'} par ordre
          </dd>
        </dl>
        <div className="ligne">
          {problemes.length ? (
            <StatusMark status="failed" label={problemes[0]} fontSize={13} />
          ) : !verifie ? (
            <StatusMark status="running" label="Le bot relit la configuration…" fontSize={13} />
          ) : verification.ok ? (
            <StatusMark status="done" label="Configuration acceptée par le bot" fontSize={13} />
          ) : (
            <StatusMark status="failed" label={verification.erreur} fontSize={13} />
          )}
        </div>
        {problemes.length > 1 && (
          <ul className="discret" style={{ margin: 0, paddingLeft: 20 }}>
            {problemes.slice(1).map(p => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        {tache && <Message genre="alerte">Une tâche tourne déjà : la GPU ne sert qu’à une à la fois.</Message>}
        {erreur && <Message genre="critique">{erreur}</Message>}
        <SlideCommit label="Glisser pour lancer l’entraînement" doneLabel="Lancé" errorLabel="Refusé" width={360} height={54} disabled={!pret} onConfirm={lancer} />
      </Carte>
    </>
  );
}
