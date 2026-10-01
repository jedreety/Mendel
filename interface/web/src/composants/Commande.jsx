// La barre de commande : aller a une page, un bot, une vue d'un bot ou un mot du lexique, au clavier. « / » liste
// les actions, « @ » les bots, un texte libre cherche partout. Ctrl+K l'ouvre de n'importe ou ; l'accueil la montre.
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useDonnees } from '../donnees.jsx';
import { lien, lienTache } from '../route.js';
import { PAGES_SYSTEME, VUES_BOT } from '../navigation.js';
import { TERMES } from '../glossaire.js';
import { libellePaire, listeBots, nomBot, useSuppressions } from '../bots.js';
import { nombre } from '../format.js';
import PromptBar from '../reactbits/PromptBar/PromptBar.jsx';

let etatOuvert = false;
const abonnes = new Set();

export function ouvrirCommande(valeur = true) {
  etatOuvert = valeur;
  abonnes.forEach(f => f());
}

function useOuverte() {
  return useSyncExternalStore(
    f => {
      abonnes.add(f);
      return () => abonnes.delete(f);
    },
    () => etatOuvert
  );
}

const norm = s =>
  String(s ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();

function useElements() {
  const { runs, tache } = useDonnees();
  const supprimes = useSuppressions();
  return useMemo(() => {
    const bots = listeBots(runs).filter(b => !supprimes.has(b.nom));
    const actions = [
      tache && { key: 'direct', name: '/direct', description: 'Suivre la tâche en cours', icon: 'lecture', href: lienTache(tache) },
      { key: 'nouveau', name: '/nouveau', description: 'Créer un bot', icon: 'plus', href: '#/entrainement/nouveau' },
      { key: 'continuer', name: '/continuer', description: 'Continuer l’entraînement d’un bot', icon: 'rafraichir', href: '#/entrainement/continuer' },
      { key: 'bots', name: '/bots', description: 'Tous les bots', icon: 'bot', href: '#/bots' },
      ...PAGES_SYSTEME.map(p => ({ key: p.cle, name: `/${p.cle}`, description: p.description, icon: p.icone, href: lien(['systeme', p.cle]) })),
      { key: 'accueil', name: '/accueil', description: 'Revenir à l’accueil', icon: 'maison', href: '#/' }
    ].filter(Boolean);
    const sources = bots.map(b => ({ key: b.nom, name: nomBot(b), description: `${libellePaire(b.symbole)} · ${nombre(b.generation)} générations`, icon: 'bot', href: lien(['bots', b.nom]) }));
    const vues = bots.flatMap(b => VUES_BOT.filter(v => v.cle !== 'resume').map(v => ({ key: `${b.nom}/${v.cle}`, name: `${nomBot(b)} · ${v.libelle}`, description: libellePaire(b.symbole), icon: v.icone, tag: 'Bot', href: lien(['bots', b.nom, v.cle]) })));
    const termes = Object.entries(TERMES).map(([id, t]) => ({ key: `terme-${id}`, name: t.terme, description: t.definition, icon: 'livre', tag: 'Lexique', href: lien(['systeme', 'lexique'], { terme: id }) }));
    const tout = [...actions.map(a => ({ ...a, tag: 'Action' })), ...sources.map(s => ({ ...s, tag: 'Bot' })), ...vues, ...termes];
    const rechercher = texte => {
      const q = norm(texte);
      return tout
        .map(e => {
          const n = norm(e.name.replace(/^\//, ''));
          return [n.startsWith(q) ? 3 : n.includes(q) ? 2 : norm(e.description).includes(q) ? 1 : 0, e];
        })
        .filter(([score]) => score > 0)
        .sort((a, b) => b[0] - a[0])
        .slice(0, 8)
        .map(([, e]) => e);
    };
    return { actions, sources, rechercher };
  }, [runs, tache, supprimes]);
}

export function BarreCommande({ placeholder = 'Aller à…  « / » une action, « @ » un bot', menuPlacement = 'bottom', autoFocus = false, onFin, width = 620 }) {
  const { actions, sources, rechercher } = useElements();
  return (
    <PromptBar
      placeholder={placeholder}
      commands={actions}
      sources={sources}
      rechercher={rechercher}
      menuPlacement={menuPlacement}
      autoFocus={autoFocus}
      width={width}
      onPick={e => {
        onFin?.();
        window.location.hash = e.href;
      }}
      onEscape={onFin}
    />
  );
}

export function CommandeFlottante() {
  const ouverte = useOuverte();
  useEffect(() => {
    const touche = e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        ouvrirCommande(!etatOuvert);
      } else if (e.key === 'Escape' && etatOuvert) ouvrirCommande(false);
    };
    window.addEventListener('keydown', touche);
    return () => window.removeEventListener('keydown', touche);
  }, []);
  return (
    <AnimatePresence>
      {ouverte && (
        <motion.div
          className="commande-voile"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onMouseDown={e => e.target === e.currentTarget && ouvrirCommande(false)}
        >
          <motion.div className="commande-boite" role="dialog" aria-label="Barre de commande" initial={{ y: -10, scale: 0.98 }} animate={{ y: 0, scale: 1 }} exit={{ y: -6, scale: 0.98 }} transition={{ duration: 0.24, ease: [0.23, 1, 0.32, 1] }}>
            <BarreCommande autoFocus onFin={() => ouvrirCommande(false)} />
            <div className="commande-aide">
              <span>
                <kbd>/</kbd> actions
              </span>
              <span>
                <kbd>@</kbd> bots
              </span>
              <span>
                <kbd>↑</kbd>
                <kbd>↓</kbd> choisir
              </span>
              <span>
                <kbd>Entrée</kbd> aller
              </span>
              <span>
                <kbd>Échap</kbd> fermer
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
