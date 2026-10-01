// Poste : GPU, processeur et memoire sur trente minutes, et d'ou l'interface lance ses taches.
import { useMemo } from 'react';
import { useDonnees, useSysteme } from '../../donnees.jsx';
import { decimal, heure, mo, nombre, octets } from '../../format.js';
import { BoutonDossier, Carte, EnTeteCarte, Vide } from '../../composants/Base.jsx';
import Courbes from '../../graphiques/Courbes.jsx';
import Graphique, { tableauDe } from '../../graphiques/Graphique.jsx';

function Mesure({ titre, sousTitre, x, valeurs, format, yMin, yMax, references }) {
  const series = useMemo(() => [{ nom: titre, couleur: 'var(--s1)', type: 'aire', valeurs }], [titre, valeurs]);
  return (
    <Carte>
      <Graphique titre={titre} sousTitre={sousTitre} tableau={() => tableauDe(x, series, 'Heure (UTC)', heure, format)}>
        {x.length > 1 ? <Courbes x={x} series={series} temps hauteur={150} formatY={format} formatX={heure} groupe="systeme" yMin={yMin} yMax={yMax} references={references} /> : <Vide titre="Mesures en attente" />}
      </Graphique>
    </Carte>
  );
}

// Une interruption des mesures (page fermee, aucune tache) laisse un trou au lieu d'une droite trompeuse.
function avecTrous(echantillons) {
  const suite = [];
  echantillons.forEach((e, i) => {
    if (i > 0 && e.t - echantillons[i - 1].t > 10) suite.push({ t: echantillons[i - 1].t + 2, vide: true });
    suite.push(e);
  });
  return suite;
}

export default function Poste() {
  const { racine } = useDonnees();
  const systeme = useSysteme();
  const courbes = useMemo(() => {
    const suite = avecTrous(systeme);
    const lire = f => suite.map(e => (e.vide ? null : f(e) ?? null));
    return {
      x: suite.map(e => e.t),
      utilisation: lire(e => e.gpu?.utilisation),
      memoire: lire(e => e.gpu?.memoire_utilisee),
      temperature: lire(e => e.gpu?.temperature),
      puissance: lire(e => e.gpu?.puissance),
      cpu: lire(e => e.cpu),
      ram: lire(e => e.memoire.utilisee / 1024 ** 3),
      botCpu: lire(e => e.bot?.cpu),
      botRam: lire(e => (e.bot ? e.bot.memoire / 1024 ** 3 : null))
    };
  }, [systeme]);
  const dernier = systeme[systeme.length - 1];
  const gpu = dernier?.gpu;
  const tacheMesuree = courbes.botCpu.some(v => v != null);
  return (
    <>
      <p className="discret">Une mesure toutes les deux secondes tant qu’une page est ouverte ou qu’une tâche tourne ; trente minutes gardées. Glissez sur un graphique pour zoomer : tous suivent.</p>
      <div className="grille grille-2">
        <Mesure titre="Utilisation de la GPU" sousTitre={gpu?.nom ?? 'nvidia-smi'} x={courbes.x} valeurs={courbes.utilisation} format={v => `${nombre(v)} %`} yMin={0} yMax={100} />
        <Mesure titre="Mémoire de la GPU" sousTitre={gpu ? `sur ${mo(gpu.memoire_totale)}, toutes applications` : ''} x={courbes.x} valeurs={courbes.memoire} format={mo} yMin={0} references={gpu ? [{ valeur: gpu.memoire_totale, libelle: 'totale' }] : []} />
        <Mesure titre="Température de la GPU" sousTitre="Degrés Celsius" x={courbes.x} valeurs={courbes.temperature} format={v => `${nombre(v)} °C`} />
        <Mesure titre="Puissance de la GPU" sousTitre="Watts" x={courbes.x} valeurs={courbes.puissance} format={v => `${decimal(v, 1)} W`} yMin={0} />
        <Mesure titre="Processeur" sousTitre={dernier ? `${dernier.coeurs} cœurs logiques` : ''} x={courbes.x} valeurs={courbes.cpu} format={v => `${nombre(v)} %`} yMin={0} yMax={100} />
        <Mesure titre="Mémoire vive" sousTitre={dernier ? `sur ${nombre(dernier.memoire.totale / 1024 ** 3, 1)} Go` : ''} x={courbes.x} valeurs={courbes.ram} format={v => `${decimal(v, 1)} Go`} yMin={0} />
        {tacheMesuree && (
          <>
            <Mesure titre="Processeur de la tâche" sousTitre="Le bot et ses rejeux, en part de la machine" x={courbes.x} valeurs={courbes.botCpu} format={v => `${decimal(v, 1)} %`} yMin={0} />
            <Mesure titre="Mémoire de la tâche" sousTitre="Le bot et ses rejeux" x={courbes.x} valeurs={courbes.botRam} format={v => `${decimal(v, 2)} Go`} yMin={0} />
          </>
        )}
      </div>
      <div className="grille grille-2">
        <Carte>
          <EnTeteCarte titre="La carte graphique" description="Dernière mesure de nvidia-smi." />
          {gpu ? (
            <dl className="cles-valeurs">
              <dt>Carte</dt>
              <dd>{gpu.nom}</dd>
              <dt>État de performance</dt>
              <dd>{gpu.etat}</dd>
              <dt>Fréquence</dt>
              <dd>
                {nombre(gpu.frequence)} MHz sur {nombre(gpu.frequence_max)} MHz
              </dd>
              <dt>Puissance</dt>
              <dd>
                {decimal(gpu.puissance, 1)} W{gpu.puissance_max != null ? ` sur ${decimal(gpu.puissance_max, 0)} W` : ''}
              </dd>
              <dt>Ventilateur</dt>
              <dd>{gpu.ventilateur != null ? `${nombre(gpu.ventilateur)} %` : 'non communiqué'}</dd>
              <dt>Disque</dt>
              <dd>
                {octets(dernier.disque.libre)} libres sur {octets(dernier.disque.total)}
              </dd>
            </dl>
          ) : (
            <Vide titre="nvidia-smi ne répond pas">Pilote NVIDIA absent ou GPU indisponible.</Vide>
          )}
        </Carte>
        <Carte>
          <EnTeteCarte titre="L’interface" description="Ce que lance le serveur, et d’où." actions={<BoutonDossier cible="etat" libelle="interface/etat" />} />
          <dl className="cles-valeurs">
            <dt>Dépôt</dt>
            <dd className="mono">{racine?.racine ?? '–'}</dd>
            <dt>Python des tâches</dt>
            <dd className="mono">{racine?.python ?? '–'}</dd>
            <dt>Sorties des tâches</dt>
            <dd className="mono">interface/etat/journaux/</dd>
            <dt>Noms des bots</dt>
            <dd className="mono">interface/etat/noms.json</dd>
          </dl>
        </Carte>
      </div>
    </>
  );
}
