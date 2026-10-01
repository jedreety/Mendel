// Les trades d'un bot sur un trimestre, rejoues dans le moteur exact : le marche en chandelles, chaque achat
// et chaque vente, les periodes tenues colorees par leur resultat, le capital, et la liste des trades. La
// lecture les revele heure par heure, comme en direct. On peut comparer a une reference du benchmark.
import { useEffect, useMemo, useRef, useState } from 'react';
import { enc, lire } from '../../api.js';
import { argent, decimal, jourHeure, nombre, pct, signe } from '../../format.js';
import { Icone, Message, Vide } from '../../composants/Base.jsx';
import Courbes, { avecAlpha } from '../../graphiques/Courbes.jsx';
import Graphique, { tableauDe } from '../../graphiques/Graphique.jsx';
import GlideSelect from '../../reactbits/GlideSelect/GlideSelect.jsx';

const HEURE = 3600;
const iso = s => new Date(s * 1000).toISOString();
const instant = texte => Date.parse(String(texte).replace(' ', 'T')) / 1000;
const RAISONS = { 'socle:stop': 'stop touché', 'socle:target': 'objectif atteint', duree: 'durée maximale', 'vente decidee': 'vente décidée', 'fin de fenetre': 'fin du trimestre' };
const VITESSES = [
  { value: 6, label: '6 h par seconde' },
  { value: 24, label: '1 jour par seconde' },
  { value: 168, label: '1 semaine par seconde' }
];
export const NOMS_REFERENCES = {
  champion: 'Votre bot',
  champion_aleatoire: 'Bot tiré au hasard',
  champion_a_blanc: 'Champion à blanc',
  champion_de_la_recherche_aleatoire: 'Recherche aléatoire',
  acheter: 'Acheter et garder'
};

function lireRejeu(nom, genre, sous, trimestre) {
  return lire(`/api/runs/${enc(nom)}/rejeu/${genre}/${enc(sous)}/${enc(trimestre)}`);
}

// Trades d'un rejeu, avec leur instant d'entree et de sortie. Une sortie par ordre au repos (stop, objectif)
// a lieu pendant la barre : elle est placee une demi-heure avant sa cloture.
export function preparerTrades(r) {
  const index = new Map(r.temps.map((t, i) => [t, i]));
  return r.trades.map(t => {
    const entree = instant(t.entry_time);
    const sortie = instant(t.exit_time) - (String(t.reason).startsWith('socle') ? HEURE / 2 : 0);
    const net = Number(t.net);
    const i = index.get(entree);
    const capital = i != null && i > 0 ? Number(r.capital[i - 1]) : Number(r.resume.capital_initial);
    return { entree, sortie, prixEntree: Number(t.entry_price), prixSortie: Number(t.exit_price), net, frais: Number(t.fees), part: net / capital, raison: RAISONS[t.reason] ?? t.reason, gain: net > 0 };
  });
}

function bilan(trades, capital0) {
  const net = trades.reduce((s, t) => s + t.net, 0);
  const gagnants = trades.filter(t => t.gain).length;
  return { n: trades.length, gagnants, net, frais: trades.reduce((s, t) => s + t.frais, 0), rendement: net / capital0 };
}

const signeDe = v => (v > 0 ? 'signe-gain' : v < 0 ? 'signe-perte' : '');

function Bilan({ nom, b, cotation, couleur }) {
  return (
    <div className="chiffre">
      <span className="chiffre-libelle">
        <i className="cle-ligne" style={{ background: couleur }} />
        {nom}
      </span>
      <span className="chiffre-valeur">
        <span className={signeDe(b.net)} />
        {signe(b.net, 2)} {cotation}
      </span>
      <span className="chiffre-detail">
        {pct(b.rendement, 2)} · {nombre(b.n)} trade{b.n > 1 ? 's' : ''} fermé{b.n > 1 ? 's' : ''}, {nombre(b.gagnants)} gagnant{b.gagnants > 1 ? 's' : ''} · frais {decimal(b.frais, 2)}
      </span>
    </div>
  );
}

export default function Trades({ nom, genre, sous, trimestres, comparables = [], cotation = '', frais = 0.001, glissement = 0.0005, decimalesPrix = 2, permutes = false }) {
  const prix = v => decimal(v, decimalesPrix);
  const [trimestre, setTrimestre] = useState(trimestres[0]);
  const [comparaison, setComparaison] = useState('');
  const [r, setR] = useState(null);
  const [autre, setAutre] = useState(null);
  const [barres, setBarres] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [pos, setPos] = useState(null);
  const [lecture, setLecture] = useState(false);
  const [vitesse, setVitesse] = useState(24);
  const reste = useRef(0);

  useEffect(() => {
    if (!trimestres.includes(trimestre)) setTrimestre(trimestres[0]);
  }, [trimestres]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let vivant = true;
    setR(null);
    setBarres(null);
    setErreur(null);
    setPos(null);
    setLecture(false);
    lireRejeu(nom, genre, sous, trimestre)
      .then(d => {
        if (!vivant) return;
        setR(d);
        if (!permutes && d.temps.length) {
          lire(`/api/prix?run=${enc(nom)}&debut=${enc(iso(d.temps[0] - HEURE))}&fin=${enc(iso(d.temps[d.temps.length - 1]))}`)
            .then(p => vivant && setBarres(p.barres))
            .catch(() => vivant && setBarres([]));
        }
      })
      .catch(e => vivant && setErreur(e.message));
    return () => {
      vivant = false;
    };
  }, [nom, genre, sous, trimestre, permutes]);

  useEffect(() => {
    let vivant = true;
    setAutre(null);
    if (!comparaison || comparaison === 'acheter') return;
    lireRejeu(nom, 'benchmark', comparaison, trimestre)
      .then(d => vivant && setAutre(d))
      .catch(() => vivant && setAutre(null));
    return () => {
      vivant = false;
    };
  }, [nom, comparaison, trimestre]);

  // Tout ce qui ne depend pas de la position de lecture.
  const base = useMemo(() => {
    if (!r) return null;
    const debut = r.prechauffage;
    const x = r.temps.slice(debut);
    const capital0 = Number(r.resume.capital_initial);
    const parOuverture = new Map((barres ?? []).map(b => [b[0], b]));
    const o = [], h = [], l = [], c = [];
    for (const t of x) {
      const b = parOuverture.get(t - HEURE);
      o.push(b ? Number(b[1]) : null);
      h.push(b ? Number(b[2]) : null);
      l.push(b ? Number(b[3]) : null);
      c.push(b ? Number(b[4]) : null);
    }
    const bas = Math.min(...l.filter(v => v != null));
    const haut = Math.max(...h.filter(v => v != null));
    const trades = preparerTrades(r).filter(t => t.entree >= x[0]);
    const capital = r.capital.slice(debut).map(Number);
    let comparee = null;
    if (comparaison === 'acheter' && o[0] != null) {
      const achat = o[0] * (1 + glissement) * (1 + frais);
      comparee = { nom: NOMS_REFERENCES.acheter, valeurs: c.map(v => (v == null ? null : (capital0 * v * (1 - glissement) * (1 - frais)) / achat)), trades: [] };
    } else if (autre) {
      const d = autre.prechauffage;
      comparee = { nom: NOMS_REFERENCES[comparaison] ?? comparaison, valeurs: autre.capital.slice(d).map(Number), trades: preparerTrades(autre).filter(t => t.entree >= x[0]) };
    }
    return { x, o, h, l, c, bas, haut, trades, capital, capital0, comparee };
  }, [r, barres, autre, comparaison, frais, glissement]);

  // Lecture : la position avance de « vitesse » heures par seconde, par pas de 100 ms.
  useEffect(() => {
    if (!lecture || !base) return;
    const id = setInterval(() => {
      reste.current += vitesse / 10;
      const pas = Math.floor(reste.current);
      reste.current -= pas;
      setPos(p => Math.min(base.x.length - 1, (p ?? 0) + pas));
    }, 100);
    return () => clearInterval(id);
  }, [lecture, vitesse, base]);
  useEffect(() => {
    if (lecture && base && pos >= base.x.length - 1) setLecture(false);
  }, [lecture, base, pos]);

  const vue = useMemo(() => {
    if (!base) return null;
    const fin = pos ?? base.x.length - 1;
    const maintenant = base.x[fin];
    const masquer = tab => tab.map((v, i) => (i <= fin ? v : null));
    const faits = base.trades.filter(t => t.sortie <= maintenant);
    const ouvert = base.trades.find(t => t.entree <= maintenant && t.sortie > maintenant);
    const marques = [];
    for (const t of base.trades) {
      if (t.entree <= maintenant) marques.push({ x: t.entree, y: t.prixEntree, sens: 'entree' });
      if (t.sortie <= maintenant) marques.push({ x: t.sortie, y: t.prixSortie, sens: 'sortie', resultat: t.gain ? 'gain' : 'perte' });
    }
    const bandes = [
      ...faits.map(t => ({ de: t.entree, a: t.sortie, couleur: avecAlpha(t.gain ? 'var(--gain)' : 'var(--perte)', 0.1) })),
      ...(ouvert ? [{ de: ouvert.entree, a: maintenant, couleur: avecAlpha('var(--s4)', 0.16) }] : [])
    ];
    const capitalSeries = [{ nom: 'Votre bot', couleur: 'var(--s1)', valeurs: masquer(base.capital) }];
    if (base.comparee) capitalSeries.push({ nom: base.comparee.nom, couleur: 'var(--s2)', valeurs: masquer(base.comparee.valeurs) });
    return {
      fin,
      maintenant,
      faits,
      ouvert,
      chandelles: { o: masquer(base.o), h: masquer(base.h), l: masquer(base.l), c: masquer(base.c), format: prix },
      marques,
      bandes,
      capitalSeries,
      bilanBot: bilan(faits, base.capital0),
      bilanAutre: base.comparee && base.comparee.trades.length ? bilan(base.comparee.trades.filter(t => t.sortie <= maintenant), base.capital0) : null,
      capitalAutre: base.comparee ? base.comparee.valeurs[fin] : null
    };
  }, [base, pos, decimalesPrix]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = [{ value: '', label: 'Aucune comparaison' }, ...comparables.map(c => ({ value: c, label: NOMS_REFERENCES[c] ?? c }))];
  const lecteurActif = pos != null;

  return (
    <div className="grille" style={{ gap: 16 }}>
      <div className="ligne">
        <GlideSelect value={trimestre} ariaLabel="Trimestre" menuWidth={140} onChange={setTrimestre} options={trimestres.map(t => ({ value: t, label: t.replace('-T', ', trimestre ') }))} />
        {comparables.length > 0 && <GlideSelect value={comparaison} ariaLabel="Comparer à" menuWidth={220} onChange={setComparaison} options={options} />}
      </div>
      {erreur && <Message genre="critique">{erreur}</Message>}
      {!r && !erreur && <Vide titre="Lecture des trades…">Le rejeu du moteur exact : trades, capital et décisions heure par heure.</Vide>}
      {vue && (
        <>
          <div className="lecteur">
            <button
              type="button"
              className="lecteur-bouton"
              onClick={() => {
                if (!lecture && (pos == null || pos >= base.x.length - 1)) setPos(0);
                setLecture(x => !x);
              }}
              aria-label={lecture ? 'Pause' : 'Rejouer comme en direct'}
              title={lecture ? 'Pause' : 'Rejouer comme en direct'}
            >
              <Icone nom={lecture ? 'pause' : 'lecture'} />
            </button>
            <input className="lecteur-curseur" type="range" min={0} max={base.x.length - 1} value={vue.fin} onChange={e => setPos(Number(e.target.value))} aria-label="Moment du trimestre" />
            <span className="lecteur-date">{jourHeure(vue.maintenant)} UTC</span>
            <GlideSelect value={vitesse} ariaLabel="Vitesse" menuWidth={200} onChange={setVitesse} options={VITESSES} size="sm" />
            {lecteurActif && (
              <button
                type="button"
                className="bouton petit discret"
                onClick={() => {
                  setLecture(false);
                  setPos(null);
                }}
              >
                Tout afficher
              </button>
            )}
          </div>
          <div className="chiffres">
            <Bilan nom="Votre bot" b={vue.bilanBot} cotation={cotation} couleur="var(--s1)" />
            {base.comparee && (
              <div className="chiffre">
                <span className="chiffre-libelle">
                  <i className="cle-ligne" style={{ background: 'var(--s2)' }} />
                  {base.comparee.nom}
                </span>
                <span className="chiffre-valeur">{vue.capitalAutre != null ? argent(vue.capitalAutre, cotation, 2) : '–'}</span>
                <span className="chiffre-detail">{vue.bilanAutre ? `${nombre(vue.bilanAutre.n)} trade${vue.bilanAutre.n > 1 ? 's' : ''} fermé${vue.bilanAutre.n > 1 ? 's' : ''}, résultat ${signe(vue.bilanAutre.net, 2)}` : 'capital à ce moment'}</span>
              </div>
            )}
            <div className="chiffre">
              <span className="chiffre-libelle">Maintenant</span>
              <span className="chiffre-valeur" style={{ fontSize: 18 }}>
                {vue.ouvert ? 'en position' : 'hors marché'}
              </span>
              <span className="chiffre-detail">{vue.ouvert ? `acheté à ${prix(vue.ouvert.prixEntree)} le ${jourHeure(vue.ouvert.entree)}` : `capital ${argent(base.capital[vue.fin], cotation, 2)}`}</span>
            </div>
          </div>
          <Graphique
            titre="Le marché et ses trades"
            sousTitre="Bougies horaires. ▲ achat ; ▼ vente, en bleu si le trade gagne, en rouge s’il perd. Les périodes tenues sont teintées de la même couleur."
            legende={[
              { nom: 'Trade gagnant', couleur: 'var(--gain)', forme: 'rect' },
              { nom: 'Trade perdant', couleur: 'var(--perte)', forme: 'rect' }
            ]}
          >
            {permutes ? (
              <Vide titre="Prix mélangés">Ce run s’entraîne et se valide sur des prix mélangés : les vrais prix ne correspondent pas à ses trades.</Vide>
            ) : barres ? (
              <Courbes x={base.x} series={[]} chandelles={vue.chandelles} trades={vue.marques} bandes={vue.bandes} temps hauteur={340} formatY={prix} formatAxeY={v => decimal(v, Math.max(decimalesPrix, 2))} formatX={v => `${jourHeure(v)} UTC`} groupe={`trades-${nom}-${sous}-${trimestre}`} yMin={base.bas} yMax={base.haut} marqueurs={lecteurActif ? [{ x: vue.maintenant, couleur: '#2a78d6' }] : []} />
            ) : (
              <Vide titre="Lecture des prix…" />
            )}
          </Graphique>
          <Graphique titre="Capital" sousTitre={`Ce que vaut le compte à chaque heure, en ${cotation || 'monnaie de cotation'}. Il part de ${argent(base.capital0, cotation)} au début du trimestre.`} legende={vue.capitalSeries.map(s => ({ nom: s.nom, couleur: s.couleur }))} tableau={() => tableauDe(base.x, vue.capitalSeries, 'Heure (UTC)', v => jourHeure(v), v => decimal(v, 2))}>
            <Courbes x={base.x} series={vue.capitalSeries} references={[{ valeur: base.capital0, libelle: 'départ' }]} temps hauteur={200} formatY={v => decimal(v, 2)} formatAxeY={v => decimal(v, 2)} formatX={v => `${jourHeure(v)} UTC`} groupe={`trades-${nom}-${sous}-${trimestre}`} />
          </Graphique>
          <div className="grille" style={{ gap: 8 }}>
            <h3>
              Ses trades {lecteurActif ? 'jusqu’ici' : 'du trimestre'} ({nombre(vue.faits.length)})
            </h3>
            {vue.faits.length || vue.ouvert ? (
              <div className="trades-liste">
                {vue.ouvert && (
                  <div className="trade en-cours">
                    <Icone nom="lecture" taille={14} />
                    <span className="trade-texte">
                      <strong>Position ouverte</strong>
                      <span>
                        achat le {jourHeure(vue.ouvert.entree)} à {prix(vue.ouvert.prixEntree)}
                      </span>
                    </span>
                    <span className="trade-resultat">en cours</span>
                  </div>
                )}
                {[...vue.faits].reverse().map(t => (
                  <div key={`${t.entree}-${t.sortie}`} className="trade">
                    <span className={signeDe(t.net)} />
                    <span className="trade-texte">
                      <strong>
                        {prix(t.prixEntree)} → {prix(t.prixSortie)}
                      </strong>
                      <span>
                        {jourHeure(t.entree)} → {jourHeure(t.sortie)} · {t.raison}
                      </span>
                    </span>
                    <span className="trade-resultat">
                      {signe(t.net, 2)} {cotation}
                      <small>{signe(t.part * 100, 2)} % du capital</small>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="discret">{lecteurActif ? 'Aucun trade fermé pour l’instant.' : 'Aucun trade ce trimestre.'}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
