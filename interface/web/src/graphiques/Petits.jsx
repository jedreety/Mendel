// Petites figures : courbe miniature des tuiles et jauge d'un rapport a une limite.
import { couleur } from './Courbes.jsx';

// Serie en gris de retrait, dernier point en couleur d'accent.
export function Sparkline({ valeurs, hauteur = 30, largeur = 120, accent = 'var(--s1)' }) {
  const finies = valeurs.filter(v => v != null && Number.isFinite(v));
  if (finies.length < 2) return <svg width={largeur} height={hauteur} />;
  const mini = Math.min(...finies);
  const maxi = Math.max(...finies);
  const etendue = maxi - mini || 1;
  const points = valeurs
    .map((v, i) => (v == null ? null : [(i / (valeurs.length - 1)) * (largeur - 6) + 3, hauteur - 4 - ((v - mini) / etendue) * (hauteur - 8)]))
    .filter(Boolean);
  const [dx, dy] = points[points.length - 1];
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} aria-hidden="true">
      <polyline points={points.map(p => p.join(',')).join(' ')} fill="none" stroke="#bababf" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={dx} cy={dy} r="3.5" fill={couleur(accent)} stroke="#ffffff" strokeWidth="2" />
    </svg>
  );
}

// Jauge : la piste est un ton clair de la meme rampe ; alerte et critique au-dela des seuils, avec leur libelle.
export function Jauge({ valeur, max, libelle, detail, seuils = [0.85, 0.95] }) {
  const part = max ? Math.max(0, Math.min(1, valeur / max)) : 0;
  const niveau = part >= seuils[1] ? 'critique' : part >= seuils[0] ? 'alerte' : '';
  return (
    <div className="jauge">
      <div className="ligne" style={{ justifyContent: 'space-between' }}>
        <span className="tuile-libelle">{libelle}</span>
        <span className="second">
          {detail}
          {niveau === 'alerte' && ' · élevé'}
          {niveau === 'critique' && ' · saturé'}
        </span>
      </div>
      <div className="jauge-piste" role="meter" aria-valuenow={valeur} aria-valuemax={max} aria-label={libelle}>
        <div className={`jauge-remplissage ${niveau}`} style={{ width: `${part * 100}%` }} />
      </div>
    </div>
  );
}
