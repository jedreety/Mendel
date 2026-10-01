// Definitions au survol : un terme souligne en pointille, ou un point d'interrogation, ouvre une bulle.
// La bulle vit dans un portail en position fixe : les cartes, qui masquent leur debordement, ne la coupent
// pas. Elle reste ouverte quand on la survole, pour suivre son lien vers le glossaire.
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { TERMES } from '../glossaire.js';
import { lien } from '../route.js';

const LARGEUR = 320;

export function Bulle({ contenu, children, className = '' }) {
  const ancre = useRef(null);
  const minuterie = useRef(null);
  const [position, setPosition] = useState(null);

  const ouvrir = () => {
    clearTimeout(minuterie.current);
    const r = ancre.current.getBoundingClientRect();
    const gauche = Math.min(Math.max(8, r.left + r.width / 2 - LARGEUR / 2), window.innerWidth - LARGEUR - 8);
    const dessous = r.bottom + 200 < window.innerHeight;
    setPosition(dessous ? { gauche, haut: r.bottom + 8 } : { gauche, bas: window.innerHeight - r.top + 8 });
  };
  const fermer = () => {
    clearTimeout(minuterie.current);
    minuterie.current = setTimeout(() => setPosition(null), 140);
  };

  useEffect(() => () => clearTimeout(minuterie.current), []);
  useEffect(() => {
    if (!position) return;
    const cacher = () => setPosition(null);
    window.addEventListener('scroll', cacher, true);
    window.addEventListener('resize', cacher);
    return () => {
      window.removeEventListener('scroll', cacher, true);
      window.removeEventListener('resize', cacher);
    };
  }, [position]);

  return (
    <span ref={ancre} className={`bulle-ancre ${className}`} tabIndex={0} onMouseEnter={ouvrir} onMouseLeave={fermer} onFocus={ouvrir} onBlur={fermer}>
      {children}
      {position &&
        createPortal(
          <div
            className="bulle-aide"
            role="tooltip"
            style={{ left: position.gauche, top: position.haut, bottom: position.bas, width: LARGEUR }}
            onMouseEnter={() => clearTimeout(minuterie.current)}
            onMouseLeave={fermer}
          >
            {contenu}
          </div>,
          document.body
        )}
    </span>
  );
}

function Definition({ id }) {
  const t = TERMES[id];
  return (
    <>
      <strong>{t.terme}</strong>
      <p>{t.definition}</p>
      <a href={lien(['systeme', 'lexique'], { terme: id })}>Voir le lexique</a>
    </>
  );
}

// <Terme id="pantheon" /> affiche « Panthéon » ; <Terme id="pantheon">le Panthéon</Terme> garde le texte.
export function Terme({ id, children }) {
  if (!TERMES[id]) return children ?? null;
  return (
    <Bulle contenu={<Definition id={id} />}>
      <span className="terme">{children ?? TERMES[id].terme}</span>
    </Bulle>
  );
}

// Point d'interrogation : la definition d'un terme du glossaire, ou un texte libre.
export function Aide({ terme, children }) {
  return (
    <Bulle contenu={terme && TERMES[terme] ? <Definition id={terme} /> : children} className="aide">
      <span className="aide-icone" aria-label="Aide">
        ?
      </span>
    </Bulle>
  );
}
