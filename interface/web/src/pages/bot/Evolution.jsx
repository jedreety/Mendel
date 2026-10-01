// Evolution d'un bot : ses notes generation apres generation, ses candidats, et pour les curieux, la force
// des mutations et la duree des generations.
import { useGenerations } from '../../donnees.jsx';
import { generationsCSV } from '../../export.js';
import { duree, nombre } from '../../format.js';
import { Carte, EnTeteCarte, Icone, Vide } from '../../composants/Base.jsx';
import Chargement from '../../composants/Chargement.jsx';
import { GraphDurees, GraphNotes, GraphSigma, GraphValidation } from '../../graphiques/Evolution.jsx';

export default function Evolution({ run }) {
  const { lignes, charge } = useGenerations(run.nom);
  const groupe = `evolution-${run.nom}`;
  if (!lignes.length) return charge ? <Vide titre="Pas encore de génération" /> : <Chargement texte="Lecture des générations" minHauteur={300} />;
  const records = [];
  let meilleure = -Infinity;
  for (const l of lignes) {
    if (l.meilleure_note_pantheon > meilleure) {
      meilleure = l.meilleure_note_pantheon;
      records.push(l.generation);
    }
  }
  return (
    <>
      <Carte>
        <GraphNotes lignes={lignes} hauteur={360} groupe={groupe} />
        <p className="discret">
          {nombre(lignes.length)} générations en {duree(run.duree_totale_s)} de calcul ; {records.length} record{records.length > 1 ? 's' : ''} de validation, le dernier à la génération {records[records.length - 1]}. Glissez sur le graphique pour zoomer, double-cliquez pour revenir.
        </p>
      </Carte>
      <Carte>
        <GraphValidation lignes={lignes} groupe={groupe} />
      </Carte>
      <details className="avances">
        <summary>
          <Icone nom="graphique" />
          Pour aller plus loin
          <span className="discret" style={{ fontWeight: 400 }}>
            mutations et durées
          </span>
        </summary>
        <div className="avances-contenu">
          <GraphSigma lignes={lignes} groupe={groupe} />
          <GraphDurees lignes={lignes} groupe={groupe} />
          <EnTeteCarte
            titre="Toutes les générations"
            description="Une ligne par génération, pour un tableur."
            actions={
              <button className="bouton petit" onClick={() => generationsCSV(run.nom, lignes)}>
                <Icone nom="telecharger" taille={15} />
                Exporter en CSV
              </button>
            }
          />
        </div>
      </details>
    </>
  );
}
