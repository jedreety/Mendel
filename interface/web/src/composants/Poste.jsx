// Mesures du poste en direct : GPU, processeur, memoire, et les processus de la tache en cours.
import { useSysteme } from '../donnees.jsx';
import { decimal, mo, nombre } from '../format.js';
import { Jauge, Sparkline } from '../graphiques/Petits.jsx';
import { Vide } from './Base.jsx';

const serie = (systeme, lire) => systeme.slice(-60).map(lire);

function Mesure({ libelle, valeur, tendance }) {
  return (
    <div className="mesure">
      <span className="tuile-libelle">{libelle}</span>
      <span className="mesure-valeur">{valeur}</span>
      <Sparkline valeurs={tendance} />
    </div>
  );
}

export default function Poste() {
  const systeme = useSysteme();
  const e = systeme[systeme.length - 1];
  if (!e) return <Vide titre="Mesures en attente">Première mesure dans deux secondes.</Vide>;
  const gpu = e.gpu;
  return (
    <div className="grille" style={{ gap: 14 }}>
      <div className="mesures">
        <Mesure libelle="GPU" valeur={gpu?.utilisation != null ? `${nombre(gpu.utilisation)} %` : '–'} tendance={serie(systeme, x => x.gpu?.utilisation)} />
        <Mesure libelle="Température GPU" valeur={gpu?.temperature != null ? `${nombre(gpu.temperature)} °C` : '–'} tendance={serie(systeme, x => x.gpu?.temperature)} />
        <Mesure libelle="Processeur" valeur={e.cpu != null ? `${nombre(e.cpu)} %` : '–'} tendance={serie(systeme, x => x.cpu)} />
        <Mesure libelle="Puissance GPU" valeur={gpu?.puissance != null ? `${decimal(gpu.puissance, 1)} W` : '–'} tendance={serie(systeme, x => x.gpu?.puissance)} />
      </div>
      {gpu && <Jauge valeur={gpu.memoire_utilisee} max={gpu.memoire_totale} libelle="Mémoire GPU, toutes applications" detail={`${mo(gpu.memoire_utilisee)} sur ${mo(gpu.memoire_totale)}`} />}
      <Jauge valeur={e.memoire.utilisee} max={e.memoire.totale} libelle="Mémoire vive" detail={`${nombre(e.memoire.utilisee / 1024 ** 3, 1)} Go sur ${nombre(e.memoire.totale / 1024 ** 3, 1)} Go`} />
      {e.bot ? (
        <p className="second" style={{ margin: 0 }}>
          Tâche : {e.bot.processus} processus (le bot et ses rejeux), {e.bot.cpu != null ? `${decimal(e.bot.cpu, 1)} % du processeur` : '–'}, {decimal(e.bot.memoire / 1024 ** 3, 2)} Go de mémoire vive.
        </p>
      ) : (
        <p className="discret" style={{ margin: 0 }}>
          Aucune tâche mesurée.
        </p>
      )}
    </div>
  );
}
