// Resume d'un bot : ce qu'il a coute en temps, son champion (une carte a son empreinte, et ce qu'il fait,
// explique simplement), puis sa progression.
import { useDiffere, useDonnees, useEffetsActifs, useGenerations } from '../../donnees.jsx';
import { aller } from '../../route.js';
import { annee, nomRun, paire } from '../../bots.js';
import { argent, compact, decimal, duree, nombre, note, pct, pctSigne } from '../../format.js';
import { Carte, Chiffre, EnTeteCarte, Vide } from '../../composants/Base.jsx';
import { Terme } from '../../composants/Aide.jsx';
import { Empreinte } from '../../composants/Empreinte.jsx';
import { GraphNotes } from '../../graphiques/Evolution.jsx';
import ProfileCard from '../../reactbits/ProfileCard/ProfileCard.jsx';
import Iridescence from '../../reactbits/Iridescence/Iridescence.jsx';
import { libelleModule } from '../../modules.js';

const ECOUTES = 12; // modules montres parmi ceux que le champion ecoute le plus
const ENTRAINEMENTS = ['nouveau', 'reprendre', 'a-blanc', 'hasard'];
const IRIS = [0.32, 0.42, 0.85];

function CarteChampion({ membre, run, runs }) {
  const differe = useDiffere();
  const effets = useEffetsActifs() && differe;
  const { base } = paire(run.symbole);
  return (
    <div className="champion-carte">
      <ProfileCard
        name="Champion"
        title={`${membre.id} · génération ${membre.generation}`}
        handle={nomRun(run, runs)}
        status={`note ${note(membre.note)}`}
        contactText={run.mode === 'reel' ? 'Ses trades' : 'Évolution'}
        onContactClick={() => aller(['bots', run.nom, run.mode === 'reel' ? 'benchmark' : 'evolution'])}
        portrait={<Empreinte parametres={membre.parametres} taille={158} />}
        fond={effets ? <Iridescence color={IRIS} speed={0.35} amplitude={0.06} /> : null}
        miniAvatar={base.slice(0, 4)}
        behindGlowColor="rgba(125, 160, 255, 0.55)"
        innerGradient="linear-gradient(145deg, #1b2a55cc 0%, #6b5bd455 100%)"
      />
    </div>
  );
}

// Ce que le champion regarde. Depuis que ses modules sont toujours allumes, les plus ecoutes : ceux dont le signal
// entre le plus fort dans les canaux du reseau. Un ancien bot montre ses huit modules, allumes ou eteints.
function Regarde({ p }) {
  if (!p.importance) {
    return (
      <div className="module-chips">
        {Object.entries(p.modules ?? {}).map(([cle, m]) => (
          <span key={cle} className={`etiquette ${m.actif ? 'accent' : 'eteint'}`} title={m.actif ? `calculé sur des bougies de ${m.echelle ?? 1} h` : 'désactivé'}>
            {libelleModule(cle)}
            {m.actif && m.echelle ? ` · ${m.echelle} h` : ''}
          </span>
        ))}
      </div>
    );
  }
  const premiers = Object.entries(p.importance).sort((a, b) => b[1] - a[1]).slice(0, ECOUTES);
  return (
    <>
      <div className="module-chips">
        {premiers.map(([cle, force]) => {
          const echelle = p.modules?.[cle]?.echelle;
          return (
            <span key={cle} className="etiquette accent" title={`écouté à ${pct(force, 0)} du module le plus écouté${echelle ? `, sur des bougies de ${echelle} h` : ''}`}>
              {libelleModule(cle)}
              {echelle ? ` · ${echelle} h` : ''}
            </span>
          );
        })}
      </div>
      <p className="discret" style={{ fontSize: 12.5, marginTop: 6 }}>Les {ECOUTES} qu’il écoute le plus, sur ses {Object.keys(p.importance).length} modules.</p>
    </>
  );
}

function Champion({ membre, run, cotation }) {
  const p = membre.parametres ?? {};
  const d = p.decision ?? {};
  const capital = Number(run.capital_initial) || 0;
  const v = membre.detail ?? {};
  const rendements = (v.capitaux ?? []).map(c => c / capital - 1);
  const trades = (v.trades ?? []).reduce((s, n) => s + n, 0);
  const anneeValidation = annee(run.debut_validation);
  return (
    <div className="champion-texte">
      <EnTeteCarte titre="Son champion" aide="champion" description={`Le meilleur de ses bots en validation, né à la génération ${membre.generation}.${run.mode === 'reel' ? ' C’est lui qui passe le benchmark.' : ''}`} />
      <div className="bloc">
        <h3>Ce qu’il regarde</h3>
        <Regarde p={p} />
      </div>
      <div className="bloc">
        <h3>Comment il trade</h3>
        <ul className="second" style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, display: 'grid', gap: 5 }}>
          {d.seuil_action != null && <li>Il n’agit que si une action dépasse {pct(d.seuil_action, 0)} de probabilité ; sinon il attend.</li>}
          {d.f_max != null && (
            <li>
              Il engage au plus <strong>{pct(d.f_max, 0)}</strong> de son capital par trade, soit {argent(d.f_max * capital, cotation)} sur {argent(capital, cotation)}.
            </li>
          )}
          {d.stop_max_propre != null && (
            <li>
              Son stop est au plus à {decimal(d.stop_max_propre, 1)} <Terme id="stopPrise">ATR</Terme> sous le prix, son objectif au plus à {decimal(d.tp_max, 1)} ATR au-dessus ; jamais plus de 5 % de perte.
            </li>
          )}
        </ul>
      </div>
      {rendements.length > 0 && (
        <div className="bloc">
          <h3>En validation{anneeValidation ? ` (${anneeValidation})` : ''}</h3>
          <p className="second" style={{ fontSize: 13.5 }}>
            {rendements.map((r, i) => `T${i + 1} ${pctSigne(r)}`).join(', ')} · {nombre(trades)} trades · Sharpe {decimal(v.sharpe_annualise, 2)}
          </p>
        </div>
      )}
    </div>
  );
}

export default function Resume({ run, detail }) {
  const { taches, runs } = useDonnees();
  const { lignes } = useGenerations(run.nom);
  const { cotation } = paire(run.symbole);
  const sessions = taches.filter(t => t.run === run.nom && ENTRAINEMENTS.includes(t.type)).length;
  const membre = detail?.pantheon?.[0];
  return (
    <>
      <div className="chiffres">
        <Chiffre libelle="Temps d’entraînement" icone="horloge" valeur={duree(run.duree_totale_s)} detail={sessions ? `calcul cumulé, en ${sessions} session${sessions > 1 ? 's' : ''}` : 'temps de calcul cumulé'} />
        <Chiffre libelle="Générations" icone="boucle" aide="generation" valeur={nombre(run.generation)} detail={`${compact(run.bots_evalues)} bots essayés`} />
        <Chiffre libelle="Meilleure note" icone="etincelle" aide="noteValidation" valeur={note(run.meilleure_note)} detail={run.generation_meilleure != null ? `trouvée à la génération ${run.generation_meilleure}` : null} />
      </div>
      {membre ? (
        <section className="champion">
          <CarteChampion membre={membre} run={run} runs={runs} />
          <Champion membre={membre} run={run} cotation={cotation} />
        </section>
      ) : (
        <p className="discret">{run.actif ? 'Son champion se lit quand il est à l’arrêt : pendant l’entraînement, son fichier change sans cesse.' : 'Pas encore de champion.'}</p>
      )}
      <Carte>{lignes.length ? <GraphNotes lignes={lignes} hauteur={280} titre="Sa progression" groupe={`resume-${run.nom}`} /> : <Vide titre="Pas encore de génération" />}</Carte>
    </>
  );
}
