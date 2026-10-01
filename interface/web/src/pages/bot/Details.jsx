// Details d'un bot : sa fiche technique, sa configuration, ses temoins et ses fichiers ; en bas, sa suppression.
import { useEffect, useState } from 'react';
import { enc, lire } from '../../api.js';
import { useDonnees } from '../../donnees.jsx';
import { aller, lien } from '../../route.js';
import { nomRun, supprimerBot } from '../../bots.js';
import { nombre, octets, quand } from '../../format.js';
import { BoutonDossier, Carte, EnTeteCarte, Icone } from '../../composants/Base.jsx';
import Chargement from '../../composants/Chargement.jsx';
import { CRITIQUE, CRITIQUE_DOUX, CRITIQUE_TEXTE } from '../../palette.js';
import FuseButton from '../../reactbits/FuseButton/FuseButton.jsx';

function Fichiers({ nom, actif }) {
  const [liste, setListe] = useState(null);
  useEffect(() => {
    let vivant = true;
    lire(`/api/runs/${enc(nom)}/fichiers`)
      .then(f => vivant && setListe(f.fichiers))
      .catch(() => vivant && setListe([]));
    return () => {
      vivant = false;
    };
  }, [nom, actif]);
  if (!liste) return <Chargement texte="Lecture des fichiers" />;
  const principaux = liste.filter(f => !f.chemin.includes('/'));
  const autres = liste.length - principaux.length;
  return (
    <>
      <ul className="liste">
        {principaux.map(f => (
          <li key={f.chemin}>
            {f.verrouille ? (
              <span className="liste-ligne" title="Le bot peut l’écrire en ce moment : il se télécharge à son arrêt">
                <Icone nom="verrou" />
                <span className="liste-texte">
                  <strong className="mono">{f.chemin}</strong>
                  <span>{octets(f.octets)} · écrit par le bot en ce moment</span>
                </span>
              </span>
            ) : (
              <a className="liste-ligne" href={`/api/runs/${enc(nom)}/fichier?chemin=${enc(f.chemin)}`} download>
                <Icone nom="telecharger" />
                <span className="liste-texte">
                  <strong className="mono">{f.chemin}</strong>
                  <span>
                    {octets(f.octets)} · modifié le {quand(f.modifie)}
                  </span>
                </span>
              </a>
            )}
          </li>
        ))}
      </ul>
      {autres > 0 && <p className="discret">Et {nombre(autres)} fichiers de rejeu dans ses sous-dossiers (pantheon/, benchmark/) : ouvrez le dossier pour les voir.</p>}
    </>
  );
}

export default function Details({ run, detail, source }) {
  const { runs } = useDonnees();
  const m = detail?.manifeste;
  const temoins = runs.filter(r => r.source === run.nom);
  return (
    <>
      <div className="grille grille-2">
        <Carte>
          <EnTeteCarte titre="Fiche technique" description="Écrite à sa création, dans manifest.json." actions={<BoutonDossier run={run.nom} />} />
          {m ? (
            <dl className="cles-valeurs">
              <dt>Dossier</dt>
              <dd className="mono">runs/{run.nom}</dd>
              <dt>Créé le</dt>
              <dd>{quand(m.date)}</dd>
              <dt>Données</dt>
              <dd className="mono">{m.donnees}</dd>
              <dt>Barres chargées</dt>
              <dd>
                {nombre(m.barres)}, dont {m.barres_comblees?.length ?? 0} heures manquantes comblées
              </dd>
              <dt>Empreinte</dt>
              <dd className="mono">{String(m.empreinte_donnees).slice(0, 20)}…</dd>
              <dt>GPU</dt>
              <dd>
                {m.gpu}, {nombre(m.memoire_gpu_mo)} Mo
              </dd>
              <dt>PyTorch</dt>
              <dd className="mono">{m.torch}</dd>
              <dt>Paquets</dt>
              <dd>{nombre(m.taille_paquet)} bots</dd>
              <dt>Révision du code</dt>
              <dd className="mono">{m.revision}</dd>
              <dt>Noyaux CUDA</dt>
              <dd className="mono">{m.noyaux ?? 'non enregistrés'}</dd>
            </dl>
          ) : (
            <Chargement />
          )}
          {detail?.etat?.noyaux?.length > 1 && <p className="discret">Ses calculs pour la GPU ont changé en cours de route (générations {detail.etat.noyaux.map(n => n.generation).join(', ')}) : il ne redonnerait pas exactement un entraînement continu.</p>}
        </Carte>
        <Carte>
          <EnTeteCarte titre="Fichiers" description="À télécharger ; les fichiers que le bot réécrit se lisent à son arrêt." />
          <Fichiers nom={run.nom} actif={run.actif} />
          {temoins.length > 0 && (
            <>
              <h3>Ses témoins</h3>
              <ul className="liste">
                {temoins.map(t => (
                  <li key={t.nom}>
                    <a className="liste-ligne" href={lien(['bots', t.nom])}>
                      <Icone nom="balance" />
                      <span className="liste-texte">
                        <strong>{nomRun(t, runs)}</strong>
                        <span className="mono">{t.nom}</span>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Carte>
      </div>
      <Carte>
        <EnTeteCarte
          titre="Configuration"
          description="Copiée dans son dossier à sa création, et relue à chaque reprise."
          actions={
            run.mode === 'reel' && (
              <a className="bouton petit" href={lien(['entrainement', 'nouveau'], { depuis: run.nom })}>
                Nouveau bot avec cette configuration
              </a>
            )
          }
        />
        {detail ? <pre className="config">{detail.config.texte}</pre> : <Chargement />}
      </Carte>
      <Carte>
        <EnTeteCarte
          titre="Supprimer ce bot"
          description={run.source ? 'Ce témoin part à la corbeille de Windows, d’où il se restaure.' : 'Son dossier et ceux de ses témoins partent à la corbeille de Windows, d’où ils se restaurent.'}
          actions={
            <FuseButton
              label="Supprimer"
              undoLabel="Annuler"
              size="md"
              background={CRITIQUE_DOUX}
              color={CRITIQUE_TEXTE}
              fuseColor={CRITIQUE}
              undoWindow={5000}
              disabled={run.actif}
              onCommit={() => {
                supprimerBot(run.nom, nomRun(run, runs), 0);
                aller(source ? ['bots', source.nom, 'benchmark'] : ['bots']);
              }}
            />
          }
        />
        {run.actif && <p className="discret">Impossible pendant qu’il est écrit.</p>}
      </Carte>
    </>
  );
}
