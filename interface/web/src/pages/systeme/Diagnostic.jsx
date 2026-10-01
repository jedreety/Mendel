// Diagnostic : tout ce qu'il faut pour entrainer, verifie sans rien lancer sur la GPU ; et la verification des
// noyaux CUDA contre leurs references, qui elle est une tache.
import { useEffect, useState } from 'react';
import { envoyer, lire } from '../../api.js';
import { useDonnees } from '../../donnees.jsx';
import { aller } from '../../route.js';
import { mo, octets, quand } from '../../format.js';
import { BoutonDossier, Carte, EnTeteCarte, Message } from '../../composants/Base.jsx';
import Chargement from '../../composants/Chargement.jsx';
import JellyRadio from '../../reactbits/JellyRadio/JellyRadio.jsx';
import StatusMark from '../../reactbits/StatusMark/StatusMark.jsx';

const MARQUES = { bon: 'done', alerte: 'cancelled', critique: 'failed', info: 'pending' };

function Controle({ statut, titre, children, action }) {
  return (
    <li>
      <StatusMark status={MARQUES[statut]} size={20} />
      <div>
        <strong>{titre}</strong>
        <span>{children}</span>
      </div>
      {action ?? <span />}
    </li>
  );
}

function Verification() {
  const { tache, rafraichir } = useDonnees();
  const [bots, setBots] = useState(256);
  const [erreur, setErreur] = useState(null);
  const lancer = async () => {
    setErreur(null);
    try {
      await envoyer('/api/taches', { type: 'verifier', bots });
      rafraichir();
      aller(['entrainement']);
    } catch (e) {
      setErreur(e.message);
    }
  };
  return (
    <Carte>
      <EnTeteCarte titre="Vérifier les calculs de la GPU" description="Après un changement des noyaux ou de PyTorch : le simulateur doit redonner sa référence et le moteur exact. Sur l’entraînement et la validation seulement, jamais sur le test." />
      <div className="ligne" style={{ gap: 14 }}>
        <span className="second">Bots comparés</span>
        <JellyRadio swell={0.14} className="rangee-jelly" size="sm" ariaLabel="Bots comparés" value={bots} onChange={setBots} items={[128, 256, 1024, 4096, 16384].map(n => ({ value: n, label: n.toLocaleString('fr-FR') }))} />
        <button className="bouton primaire" onClick={lancer} disabled={!!tache}>
          Lancer la vérification
        </button>
        {tache && <span className="discret">Une tâche tourne déjà.</span>}
      </div>
      {erreur && <Message genre="critique">{erreur}</Message>}
    </Carte>
  );
}

export default function Diagnostic() {
  const { tache } = useDonnees();
  const [d, setD] = useState(null);
  const [torch, setTorch] = useState(null);
  const charger = () => {
    setD(null);
    lire('/api/diagnostic')
      .then(setD)
      .catch(e => setD({ erreur: e.message }));
  };
  useEffect(charger, []);
  const controlerTorch = async () => {
    setTorch({ enCours: true });
    try {
      setTorch(await envoyer('/api/diagnostic/torch'));
    } catch (e) {
      setTorch({ ok: false, erreur: e.message });
    }
  };

  if (!d) return <Chargement texte="Contrôles en cours" minHauteur={260} />;
  if (d.erreur) return <Message genre="critique">{d.erreur}</Message>;

  const gpuLibre = d.gpu ? d.gpu.memoire_totale - d.gpu.memoire_utilisee : null;
  const bloquants = [!d.python.venv, !d.gpu, !d.donnees.existe, !!d.configuration.erreur, d.disque.libre < 2 * 1024 ** 3, torch && !torch.enCours && !(torch.ok && torch.disponible)].filter(Boolean).length;
  return (
    <>
      <Carte>
        <EnTeteCarte
          titre={bloquants ? `${bloquants} point${bloquants > 1 ? 's' : ''} à corriger avant d’entraîner` : 'Prêt à entraîner'}
          description={bloquants ? null : torch?.ok ? 'Tout est en place.' : 'Il reste à contrôler PyTorch, en un clic.'}
          actions={
            <button className="bouton petit" onClick={charger}>
              Refaire le diagnostic
            </button>
          }
        />
        <ul className="pas-a-pas">
          <Controle statut={d.python.venv ? 'bon' : 'alerte'} titre="Python des tâches">
            {d.python.version} · <span className="mono">{d.python.chemin}</span>
            {!d.python.venv && ' · ce n’est pas le venv du dépôt : PyTorch pourrait y manquer.'}
          </Controle>
          <Controle
            statut={!torch || torch.enCours ? 'info' : torch.ok && torch.disponible ? 'bon' : 'critique'}
            titre="PyTorch et CUDA"
            action={
              <button className="bouton petit" onClick={controlerTorch} disabled={!!tache || torch?.enCours} title={tache ? 'Pendant une tâche, ce contrôle ouvrirait CUDA à côté du bot' : undefined}>
                {torch?.enCours ? 'Contrôle…' : 'Contrôler'}
              </button>
            }
          >
            {!torch && (tache ? 'Bloqué pendant une tâche : il ouvrirait CUDA à côté du bot.' : 'Importe torch dans un processus à part, en quelques secondes.')}
            {torch?.enCours && 'Import de torch…'}
            {torch && !torch.enCours && (torch.ok ? `PyTorch ${torch.version}, CUDA ${torch.cuda}, ${torch.disponible ? `${torch.cartes} GPU visible${torch.cartes > 1 ? 's' : ''}` : 'CUDA indisponible'}` : torch.erreur)}
          </Controle>
          <Controle statut={d.gpu ? 'bon' : 'critique'} titre="Carte graphique et pilote NVIDIA">
            {d.gpu ? `${d.gpu.nom}, pilote ${d.pilote ?? '?'} · ${mo(gpuLibre)} libres sur ${mo(d.gpu.memoire_totale)} · ${d.gpu.temperature} °C` : 'nvidia-smi ne répond pas : pilote absent ou GPU indisponible.'}
          </Controle>
          <Controle statut={d.donnees.existe ? 'bon' : 'critique'} titre="Données du bot par défaut">
            <span className="mono">{d.donnees.chemin}</span>
            {d.donnees.existe ? ` · ${octets(d.donnees.octets)}, préparé le ${quand(d.donnees.modifie)}` : ' · absent : téléchargez-le depuis Données.'}
          </Controle>
          <Controle statut={d.configuration.erreur ? 'critique' : 'bon'} titre="Configuration par défaut">
            <span className="mono">{d.configuration.chemin}</span> · {d.configuration.erreur ?? 'acceptée par le lecteur du bot'}
          </Controle>
          <Controle statut={d.disque.libre > 10 * 1024 ** 3 ? 'bon' : d.disque.libre > 2 * 1024 ** 3 ? 'alerte' : 'critique'} titre="Espace disque">
            {octets(d.disque.libre)} libres sur {octets(d.disque.total)}. Un bot de 50 générations écrit quelques dizaines de mégaoctets.
          </Controle>
          <Controle statut="info" titre="Calculs compilés pour la GPU">
            {d.noyaux.existe ? `${d.noyaux.fichiers} noyaux, ${octets(d.noyaux.octets)}. Ils s’effacent sans risque : le prochain lancement les recompile.` : 'Aucun : le prochain lancement les compile, en quelques secondes.'} <span className="mono discret">{d.noyaux.chemin}</span>
          </Controle>
          <Controle statut={d.web.construit ? 'bon' : 'alerte'} titre="Application web">
            {d.web.construit ? `Construite le ${quand(d.web.modifie)}.` : 'Non construite : cd interface/web, npm install, npm run build.'}
          </Controle>
          <Controle statut="info" titre="État de l’interface" action={d.etat_interface.existe ? <BoutonDossier cible="etat" libelle="Ouvrir" /> : null}>
            {d.etat_interface.existe ? `${d.etat_interface.fichiers} fichiers : tâches, sorties, configurations lancées et noms des bots, ${octets(d.etat_interface.octets)}.` : 'Vide : aucune tâche lancée depuis l’interface.'}
          </Controle>
        </ul>
      </Carte>
      <Verification />
    </>
  );
}
