// Notifications : ce qui vient de se passer, tire des mises a jour du serveur. Chacune est un SwipeToast de React
// Bits : sa meche montre le temps qui reste et s'arrete au survol, un glissement vers le bas la ferme, un clic sur
// son texte mene a la page qui en parle ; elle peut porter une action (« Annuler »). Si l'utilisateur l'a demande,
// le navigateur les montre aussi quand l'onglet est cache.
import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useDonnees } from '../donnees.jsx';
import { TYPES_TACHES, note } from '../format.js';
import { lien, lienTache } from '../route.js';
import { ACCENT, ALERTE, BON, CRITIQUE } from '../palette.js';
import SwipeToast from '../reactbits/SwipeToast/SwipeToast.jsx';
import Icone from './Icone.jsx';

let liste = [];
let prochain = 1;
const abonnes = new Set();
const publier = () => abonnes.forEach(f => f());

export function retirer(id) {
  liste = liste.filter(t => t.id !== id);
  publier();
}

// La notification se ferme d'elle-meme au bout de sa meche (SwipeToast) ; la duree ne court pas pendant le survol.
export function notifier({ genre = '', titre, texte, href, duree = 7000, action, meche = false }) {
  const t = { id: prochain++, genre, titre, texte, href, action, meche, duree };
  liste = [...liste, t].slice(-4);
  publier();
  try {
    if (document.visibilityState === 'hidden' && localStorage.getItem('notifications') === 'oui' && Notification.permission === 'granted') {
      new Notification(titre, { body: texte ?? '' });
    }
  } catch {
    /* notifications du navigateur indisponibles */
  }
}

const ICONES = { bon: 'coche', critique: 'croix', alerte: 'alerte', actif: 'eclair' };
const TEINTES = { bon: BON, critique: CRITIQUE, alerte: '#b77b00', actif: ACCENT };

export function Toasts() {
  const toasts = useSyncExternalStore(
    f => {
      abonnes.add(f);
      return () => abonnes.delete(f);
    },
    () => liste
  );
  return (
    <div className="toasts">
      {toasts.map(t => (
        <SwipeToast
          key={t.id}
          inline
          title={t.titre}
          description={t.texte}
          icon={
            <span style={{ color: TEINTES[t.genre] ?? '#55555d', display: 'inline-flex' }}>
              <Icone nom={ICONES[t.genre] ?? 'info'} taille={18} />
            </span>
          }
          actionLabel={t.action?.libelle ?? ''}
          onAction={t.action?.faire}
          onOpen={t.href ? () => (window.location.hash = t.href) : undefined}
          closeButton={!t.action}
          duration={t.duree}
          pauseOnHover={!t.meche}
          fuseColor={t.meche ? CRITIQUE : t.genre === 'alerte' ? ALERTE : ACCENT}
          width={380}
          radius={14}
          onClose={() => retirer(t.id)}
        />
      ))}
    </div>
  );
}

const FINS = {
  terminee: ['bon', 'terminé'],
  arretee: ['bon', 'arrêté proprement'],
  interrompue: ['alerte', 'interrompu'],
  echec: ['critique', 'en échec'],
  tuee: ['critique', 'arrêté de force']
};

// Compare chaque mise a jour a la precedente. Rien n'est notifie tant qu'une liste n'a pas ete lue une fois :
// l'historique n'est pas une nouvelle.
export function useEvenements() {
  const { taches, runs, pret } = useDonnees();
  const avant = useRef(null);
  useEffect(() => {
    const p = avant.current;
    avant.current = { taches, runs, pret };
    if (!p) return;
    if (p.pret.taches) {
      for (const t of taches) {
        const ancienne = p.taches.find(x => x.id === t.id);
        if (!ancienne) {
          notifier({ genre: 'actif', titre: `${TYPES_TACHES[t.type]} lancé`, texte: t.nom || t.symbole || '', href: lienTache(t) });
        } else if (ancienne.etat !== t.etat) {
          if (t.etat === 'arret demande') notifier({ genre: 'alerte', titre: 'Arrêt demandé', texte: 'Le bot finit la génération en cours, sauvegarde, puis rejoue son Panthéon.' });
          else if (FINS[t.etat]) {
            const [genre, libelle] = FINS[t.etat];
            const bot = t.source ?? t.run;
            notifier({
              genre,
              titre: `${TYPES_TACHES[t.type]} ${libelle}`,
              texte: genre === 'bon' ? '' : 'La sortie de la tâche dit pourquoi.',
              href: genre === 'bon' && bot ? lien(['bots', bot]) : '#/systeme/taches',
              duree: genre === 'bon' ? 8000 : 15000
            });
          }
        }
      }
    }
    if (p.pret.runs) {
      for (const r of runs) {
        const ancien = p.runs.find(x => x.nom === r.nom);
        if (!ancien || r.mode !== 'reel') continue;
        if (r.meilleure_note != null && ancien.meilleure_note != null && r.meilleure_note > ancien.meilleure_note) {
          notifier({ genre: 'bon', titre: `Nouveau record : ${note(r.meilleure_note)}`, texte: `Génération ${r.generation_meilleure}`, href: '#/entrainement' });
        }
      }
    }
  }, [taches, runs, pret]);
}
