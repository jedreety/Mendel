// Briques communes des pages : cartes, en-tetes, chiffres, messages, onglets, progression.
import { useState } from 'react';
import { envoyer } from '../api.js';
import { useMaintenant } from '../donnees.jsx';
import { ilya } from '../format.js';
import RubberSegment from '../reactbits/RubberSegment/RubberSegment.jsx';
import Icone from './Icone.jsx';
import { Aide } from './Aide.jsx';

export { default as Icone } from './Icone.jsx';

export function Carte({ children, className = '', onClick, titre }) {
  return (
    <section className={`carte ${onClick ? 'cliquable' : ''} ${className}`} onClick={onClick} aria-label={titre}>
      {children}
    </section>
  );
}

// En-tete d'une page : bouton de retour a gauche s'il y a ou revenir, titre, phrase d'usage, actions.
export function EnTete({ titre, description, surtitre, retour, actions, children }) {
  return (
    <header className="entete">
      <div className="ligne" style={{ alignItems: 'flex-start', gap: 14, flexWrap: 'nowrap', minWidth: 0 }}>
        {retour && (
          <a className="retour" href={retour} title="Revenir" aria-label="Revenir">
            <Icone nom="retour" taille={18} />
          </a>
        )}
        <div className="entete-texte">
          {surtitre && <div className="surtitre">{surtitre}</div>}
          <h1>{titre}</h1>
          {description && <p>{description}</p>}
          {children}
        </div>
      </div>
      {actions && <div className="entete-actions">{actions}</div>}
    </header>
  );
}

export function EnTeteCarte({ titre, description, aide, actions }) {
  return (
    <div className="carte-entete">
      <div>
        <h2>
          {titre}
          {aide && <Aide terme={aide} />}
        </h2>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="ligne">{actions}</div>}
    </div>
  );
}

// Un chiffre cle : libelle discret, valeur, et une ligne qui dit ce qu'elle veut dire.
export function Chiffre({ libelle, valeur, detail, aide, icone }) {
  return (
    <div className="chiffre">
      <span className="chiffre-libelle">
        {icone && <Icone nom={icone} taille={14} />}
        {libelle}
        {aide && <Aide terme={aide} />}
      </span>
      <span className="chiffre-valeur">{valeur ?? '–'}</span>
      {detail && <span className="chiffre-detail">{detail}</span>}
    </div>
  );
}

export function Message({ genre = '', children }) {
  const icone = { critique: 'croix', alerte: 'alerte', bon: 'coche' }[genre] ?? 'info';
  return (
    <div className={`message ${genre}`} role={genre === 'critique' ? 'alert' : undefined}>
      <Icone nom={icone} taille={16} />
      <div>{children}</div>
    </div>
  );
}

export function Vide({ titre, children }) {
  return (
    <div className="vide">
      <strong>{titre}</strong>
      {children}
    </div>
  );
}

// Onglets : des liens (href) ou des boutons (onClick). L'actif est marque pour les lecteurs d'ecran.
export function Onglets({ elements, actif, etiquette = 'Onglets' }) {
  return (
    <nav className="onglets" aria-label={etiquette}>
      {elements.map(e =>
        e.href ? (
          <a key={e.cle} href={e.href} aria-current={e.cle === actif ? 'page' : undefined}>
            {e.icone && <Icone nom={e.icone} taille={15} />}
            {e.libelle}
          </a>
        ) : (
          <button key={e.cle} type="button" aria-pressed={e.cle === actif} onClick={e.onClick}>
            {e.icone && <Icone nom={e.icone} taille={15} />}
            {e.libelle}
          </button>
        )
      )}
    </nav>
  );
}

// Segments : un curseur qui glisse d'un choix a l'autre (RubberSegment de React Bits). Chaque element est un lien
// (href), une action (onClick), ou une simple valeur remontee par onChange.
export function Segments({ elements, actif, onChange, etiquette = 'Vues', taille = 'md', egaux = false }) {
  return (
    <RubberSegment
      items={elements.map(e => ({ value: e.cle, label: e.libelle, icon: e.icone ? <Icone nom={e.icone} taille={taille === 'sm' ? 13 : 15} /> : null }))}
      value={actif}
      aria-label={etiquette}
      size={taille}
      equalSlots={egaux}
      onChange={cle => {
        const e = elements.find(x => x.cle === cle);
        if (e?.href) window.location.hash = e.href;
        else if (e?.onClick) e.onClick();
        onChange?.(cle);
      }}
    />
  );
}

// Barre de progression : part entre 0 et 1, ou null pour une progression continue sans fin connue.
export function Progression({ part, gauche, droite, continu = false }) {
  const p = part == null ? 0 : Math.max(0, Math.min(1, part));
  return (
    <div className="progression">
      {(gauche || droite) && (
        <div className="progression-ligne">
          <span>{gauche}</span>
          <span>{droite}</span>
        </div>
      )}
      <div className={`progression-piste ${continu ? 'continue' : ''}`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)}>
        <div className="progression-remplissage" style={{ width: `${p * 100}%` }} />
      </div>
    </div>
  );
}

// « il y a 3 min », tenu a jour chaque seconde.
export function Depuis({ instant }) {
  const maintenant = useMaintenant();
  return <>{ilya(instant, maintenant)}</>;
}

export function Copier({ texte, libelle = 'Copier' }) {
  const [fait, setFait] = useState(false);
  const copier = async e => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(texte);
      setFait(true);
      setTimeout(() => setFait(false), 1500);
    } catch {
      /* presse-papiers refuse : rien a faire */
    }
  };
  return (
    <button className="bouton petit" onClick={copier} title="Copier dans le presse-papiers">
      {fait ? 'Copié' : libelle}
    </button>
  );
}

// Montre le dossier d'un run, ou l'un de ses fichiers, dans l'Explorateur de Windows.
export function BoutonDossier({ run, chemin, cible, libelle = 'Ouvrir le dossier' }) {
  const [erreur, setErreur] = useState(null);
  const ouvrir = async e => {
    e.stopPropagation();
    try {
      await envoyer('/api/ouvrir', run ? { run, chemin } : { cible });
      setErreur(null);
    } catch (err) {
      setErreur(err.message);
    }
  };
  return (
    <button className="bouton petit" onClick={ouvrir} title={erreur ?? 'Montrer dans l’Explorateur'}>
      <Icone nom="dossier" taille={15} />
      {libelle}
    </button>
  );
}
