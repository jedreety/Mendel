// Cadre d'un graphique : titre, legende (des deux series), et bascule vers un tableau des memes valeurs,
// pour que rien ne soit lisible seulement au survol.
import { useState } from 'react';
import { couleur } from './Courbes.jsx';

export function Legende({ elements }) {
  if (!elements || elements.length < 2) return null;
  return (
    <div className="legende">
      {elements.map(e => (
        <span key={e.nom}>
          <i className={e.forme === 'points' ? 'cle-point' : e.forme === 'rect' ? 'cle-rect' : 'cle-ligne'} style={{ background: couleur(e.couleur) }} />
          {e.nom}
        </span>
      ))}
    </div>
  );
}

export function TableauDonnees({ colonnes, lignes, limite = 1000 }) {
  const affichees = lignes.length > limite ? lignes.slice(-limite) : lignes;
  return (
    <div className="tableau-conteneur">
      <table className="tableau">
        <thead>
          <tr>
            {colonnes.map(c => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...affichees].reverse().map((ligne, i) => (
            <tr key={i}>
              {ligne.map((v, j) => (
                <td key={j}>{v ?? '–'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Tableau des valeurs d'un graphique de courbes : une ligne par abscisse, une colonne par serie.
export function tableauDe(x, series, nomX, formatX, formatY) {
  return {
    colonnes: [nomX, ...series.filter(s => !s.cache).map(s => s.nom)],
    lignes: x.map((v, i) => [formatX ? formatX(v) : v, ...series.filter(s => !s.cache).map(s => (s.valeurs[i] == null ? null : (s.format ?? formatY)(s.valeurs[i])))])
  };
}

export default function Graphique({ titre, sousTitre, legende, tableau, actions, children }) {
  const [vue, setVue] = useState('graphique');
  return (
    <>
      <div className="carte-entete">
        <div>
          <h2>{titre}</h2>
          {sousTitre && <p>{sousTitre}</p>}
        </div>
        <div className="ligne">
          {actions}
          {tableau && (
            <button className="bouton petit" onClick={() => setVue(v => (v === 'graphique' ? 'tableau' : 'graphique'))}>
              {vue === 'graphique' ? 'Tableau' : 'Graphique'}
            </button>
          )}
        </div>
      </div>
      <Legende elements={legende} />
      {vue === 'graphique' || !tableau ? children : <TableauDonnees {...(typeof tableau === 'function' ? tableau() : tableau)} />}
    </>
  );
}
