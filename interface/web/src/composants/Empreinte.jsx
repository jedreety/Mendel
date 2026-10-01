// Deux images tirees des bots eux-memes, en guise de portraits.
// L'empreinte d'un bot : ses huit modules de signal d'origine en couronne, colores selon leur echelle (1, 4 ou 24
// heures) quand ils sont actifs, ce qu'ils sont toujours depuis que tous les modules sont allumes ; en arc
// interieur, la part de capital qu'il engage au plus par trade. Chaque champion a la sienne.
// Le genome : une grille de seize cases coloriees d'apres une graine, pour les cartes de l'helice.
import { PASTELS } from '../palette.js';

const ORDRE = ['premiere_bougie', 'croisement', 'rsi', 'cassure', 'momentum', 'volatilite_relative', 'volume_relatif', 'retour_moyenne'];
const ECHELLES = { 1: PASTELS.bleu, 4: '#c3b2ff', 24: '#8fe3f2' };

const polaire = (r, degres) => {
  const a = (degres * Math.PI) / 180;
  return `${(100 + r * Math.cos(a)).toFixed(2)} ${(100 + r * Math.sin(a)).toFixed(2)}`;
};
const arc = (r, a0, a1) => `M ${polaire(r, a0)} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${polaire(r, a1)}`;

export function Empreinte({ parametres, taille = 170 }) {
  const modules = parametres?.modules ?? {};
  const part = Math.max(0, Math.min(0.999, Number(parametres?.decision?.f_max ?? 0)));
  return (
    <svg viewBox="0 0 200 200" width={taille} height={taille} aria-hidden="true">
      <circle cx="100" cy="100" r="95" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="1" strokeDasharray="1.5 5" />
      {ORDRE.map((cle, i) => {
        const m = modules[cle];
        const a0 = i * 45 - 90 + 4;
        const actif = m && m.actif !== false;
        return <path key={cle} d={arc(73, a0, a0 + 37)} fill="none" stroke={actif ? ECHELLES[m.echelle] ?? PASTELS.bleu : 'rgba(255,255,255,0.14)'} strokeWidth="15" strokeLinecap="round" />;
      })}
      <circle cx="100" cy="100" r="48" fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth="1.5" />
      {part > 0 && <path d={arc(48, -90, -90 + 360 * part)} fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" />}
      <circle cx="100" cy="100" r="7" fill="#ffffff" />
    </svg>
  );
}

const TEINTES = [PASTELS.bleu, PASTELS.lavande, PASTELS.ciel, PASTELS.rose, '#2a78d6', '#7b61ff'];

function hacher(texte) {
  let h = 2166136261;
  for (let i = 0; i < texte.length; i++) h = Math.imul(h ^ texte.charCodeAt(i), 16777619);
  return h >>> 0;
}

export function Genome({ graine }) {
  const h = hacher(String(graine));
  return (
    <div className="genome" aria-hidden="true">
      {Array.from({ length: 16 }, (_, i) => {
        const v = hacher(`${h}:${i}`);
        return <i key={i} style={v % 5 < 2 ? undefined : { background: TEINTES[v % TEINTES.length] }} />;
      })}
    </div>
  );
}
