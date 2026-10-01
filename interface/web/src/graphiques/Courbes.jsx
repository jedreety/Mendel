// Courbes temporelles sur uPlot (canvas, rapide sur des milliers de points). Traits de 2 px, grille en filets,
// infobulle qui liste toutes les series a l'abscisse du curseur, glisser pour zoomer, double-clic pour revenir.
// Les graphiques d'un meme groupe partagent curseur et zoom.
import { useEffect, useLayoutEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

const MUET = '#8e8e96';
const GRILLE = '#f0f0f2';
const AXE = '#dedee3';
const SURFACE = '#ffffff';
const ENCRE = '#111113';
const RESULTATS = { gain: '#2a78d6', perte: '#e34948' };
const zooms = new Map(); // groupe -> Set des graphiques qui partagent le zoom

export function couleur(valeur) {
  if (!valeur?.startsWith('var(')) return valeur;
  return getComputedStyle(document.documentElement).getPropertyValue(valeur.slice(4, -1)).trim();
}

export function avecAlpha(hex, alpha) {
  const h = couleur(hex).replace('#', '');
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const utc = ts => uPlot.tzDate(new Date(ts * 1e3), 'Etc/UTC');

// Axes de temps en francais, sur 24 heures. Meme structure que la table par defaut d'uPlot :
// pas minimal (secondes), format courant, puis formats au changement d'annee, de mois, de jour, d'heure, de minute.
const NOMS_DATES = {
  MMMM: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  MMM: ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
  WWWW: ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'],
  WWW: ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']
};
const fmtDate = modele => uPlot.fmtDate(modele, NOMS_DATES);
const _ = null;
const JOUR = 86400;
const VALEURS_TEMPS = [
  [JOUR * 365, '{YYYY}', _, _, _, _, _, _, 1],
  [JOUR * 28, '{MMM}', '\n{YYYY}', _, _, _, _, _, 1],
  [JOUR, '{D} {MMM}', '\n{YYYY}', _, _, _, _, _, 1],
  [3600, '{HH}:{mm}', '\n{D} {MMM} {YYYY}', _, '\n{D} {MMM}', _, _, _, 1],
  [60, '{HH}:{mm}', '\n{D} {MMM} {YYYY}', _, '\n{D} {MMM}', _, _, _, 1],
  [1, '{HH}:{mm}:{ss}', '\n{D} {MMM} {YYYY}', _, '\n{D} {MMM}', _, _, _, 1]
];

function bornesVisibles(u) {
  const [a, b] = u.series[0].idxs ?? [0, u.data[0].length - 1];
  return [Math.max(0, a), Math.min(u.data[0].length - 1, b)];
}

function texte(u, chaine, x, y, alignement = 'left', teinte = '#55555d') {
  const ctx = u.ctx;
  ctx.fillStyle = teinte;
  ctx.font = `${11 * uPlot.pxRatio}px system-ui, sans-serif`;
  ctx.textAlign = alignement;
  ctx.textBaseline = 'top';
  ctx.fillText(chaine, x, y);
}

function dessinerBandes(u, bandes) {
  const ctx = u.ctx;
  const { left, top, width, height } = u.bbox;
  const px = uPlot.pxRatio;
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, width, height);
  ctx.clip();
  for (const b of bandes) {
    const x0 = Math.max(left, u.valToPos(b.de, 'x', true));
    const x1 = Math.min(left + width, u.valToPos(b.a, 'x', true));
    if (x1 <= x0) continue;
    if (b.couleur) {
      ctx.fillStyle = b.couleur;
      ctx.fillRect(x0, top, x1 - x0, height);
    }
    if (b.hachure) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(x0, top, x1 - x0, height); // les diagonales ne sortent pas de leur bande
      ctx.clip();
      ctx.strokeStyle = 'rgba(137, 137, 145, 0.35)';
      ctx.lineWidth = px;
      ctx.beginPath();
      for (let x = x0 - height; x < x1; x += 10 * px) {
        ctx.moveTo(x, top + height);
        ctx.lineTo(x + height, top);
      }
      ctx.stroke();
      ctx.restore();
    }
    if (b.libelle && x1 - x0 > 40 * px) texte(u, b.libelle, x0 + 5 * px, b.bas ? top + height - 17 * px : top + 5 * px, 'left', b.teinteLibelle ?? '#55555d');
  }
  ctx.restore();
}

function dessinerReperes(u, references, marqueurs) {
  const ctx = u.ctx;
  const { left, top, width, height } = u.bbox;
  const px = uPlot.pxRatio;
  ctx.save();
  ctx.lineWidth = px;
  for (const r of references) {
    const y = Math.round(u.valToPos(r.valeur, 'y', true)) + 0.5;
    if (y < top || y > top + height) continue;
    ctx.strokeStyle = r.couleur ?? '#bababf';
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(left + width, y);
    ctx.stroke();
    if (r.libelle) texte(u, r.libelle, left + width - 4 * px, y + 3 * px, 'right', MUET);
  }
  // Nombreux, les reperes sans couleur propre (les nouveaux lots) ne sont plus que des tirets en haut du trace ; un
  // libelle ne s'ecrit que s'il a la place.
  const visibles = marqueurs.filter(m => {
    const x = u.valToPos(m.x, 'x', true);
    return x >= left && x <= left + width;
  });
  const serres = visibles.filter(m => !m.couleur).length > 12;
  let dernierLibelle = -Infinity;
  for (const m of visibles) {
    const x = Math.round(u.valToPos(m.x, 'x', true)) + 0.5;
    const tiret = serres && !m.couleur;
    ctx.strokeStyle = m.couleur ?? '#cfcfd4';
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, tiret ? top + 5 * px : top + height);
    ctx.stroke();
    if (m.libelle && !tiret && x - dernierLibelle > 110 * px) {
      texte(u, m.libelle, x + 3 * px, top + 3 * px, 'left', MUET);
      dernierLibelle = x;
    }
  }
  ctx.restore();
}

// Chandelles en retrait : le prix est le contexte, les decisions du bot sont le sujet. Creuses a la hausse.
function dessinerChandelles(u, { o, h, l, c }) {
  const ctx = u.ctx;
  const [a, b] = bornesVisibles(u);
  const px = uPlot.pxRatio;
  const pas = u.bbox.width / Math.max(1, b - a + 1);
  const largeur = Math.max(px, Math.min(10 * px, pas * 0.62));
  ctx.save();
  ctx.beginPath();
  ctx.rect(u.bbox.left, u.bbox.top, u.bbox.width, u.bbox.height);
  ctx.clip();
  ctx.lineWidth = px;
  for (let i = a; i <= b; i++) {
    if (o[i] == null) continue;
    const x = u.valToPos(u.data[0][i], 'x', true);
    const yo = u.valToPos(o[i], 'y', true);
    const yc = u.valToPos(c[i], 'y', true);
    const hausse = c[i] >= o[i];
    ctx.strokeStyle = hausse ? '#a3a3ab' : '#b8b8bf';
    ctx.beginPath();
    ctx.moveTo(Math.round(x) + 0.5, u.valToPos(h[i], 'y', true));
    ctx.lineTo(Math.round(x) + 0.5, u.valToPos(l[i], 'y', true));
    ctx.stroke();
    const haut = Math.min(yo, yc);
    const hauteur = Math.max(px, Math.abs(yc - yo));
    if (hausse) {
      ctx.fillStyle = SURFACE;
      ctx.fillRect(x - largeur / 2, haut, largeur, hauteur);
      if (largeur > 2 * px) ctx.strokeRect(x - largeur / 2, haut, largeur, hauteur);
    } else {
      ctx.fillStyle = '#c9c9cf';
      ctx.fillRect(x - largeur / 2, haut, largeur, hauteur);
    }
  }
  ctx.restore();
}

// Entrees et sorties : un triangle sous le cours a l'achat, au-dessus a la vente, cercle de la surface pour
// rester lisible sur les chandelles. La vente prend la couleur du resultat du trade : gain ou perte.
function dessinerTrades(u, trades) {
  const ctx = u.ctx;
  const px = uPlot.pxRatio;
  const { left, top, width, height } = u.bbox;
  const t = 6 * px;
  ctx.save();
  for (const m of trades) {
    const x = u.valToPos(m.x, 'x', true);
    const y = u.valToPos(m.y, 'y', true);
    if (x < left || x > left + width || y < top || y > top + height) continue;
    ctx.beginPath();
    if (m.sens === 'entree') {
      ctx.moveTo(x, y + 3 * px);
      ctx.lineTo(x - t, y + 3 * px + t * 1.5);
      ctx.lineTo(x + t, y + 3 * px + t * 1.5);
    } else {
      ctx.moveTo(x, y - 3 * px);
      ctx.lineTo(x - t, y - 3 * px - t * 1.5);
      ctx.lineTo(x + t, y - 3 * px - t * 1.5);
    }
    ctx.closePath();
    ctx.lineWidth = 2 * px;
    ctx.strokeStyle = SURFACE;
    ctx.stroke();
    ctx.fillStyle = m.sens === 'entree' ? ENCRE : RESULTATS[m.resultat] ?? MUET;
    ctx.fill();
  }
  ctx.restore();
}

function remplirInfobulle(u, bulle, props) {
  const idx = u.cursor.idx;
  if (idx == null || u.cursor.left == null || u.cursor.left < 0) {
    bulle.style.display = 'none';
    return;
  }
  const { series, formatX, formatY, chandelles } = props.current;
  const x = u.data[0][idx];
  bulle.replaceChildren();
  const titre = document.createElement('div');
  titre.className = 'ib-titre';
  titre.textContent = formatX ? formatX(x) : String(x);
  bulle.appendChild(titre);
  const ligne = (teinte, valeur, nom, forme = 'ligne') => {
    const div = document.createElement('div');
    div.className = 'ib-ligne';
    const cle = document.createElement('span');
    cle.className = forme === 'points' ? 'cle-point' : 'cle-ligne';
    cle.style.background = teinte;
    const v = document.createElement('span');
    v.className = 'ib-valeur';
    v.textContent = valeur;
    const n = document.createElement('span');
    n.className = 'ib-nom';
    n.textContent = nom;
    div.append(cle, v, n);
    bulle.appendChild(div);
  };
  if (chandelles) {
    const f = chandelles.format ?? formatY;
    for (const [nom, tab] of [['ouverture', chandelles.o], ['haut', chandelles.h], ['bas', chandelles.l], ['clôture', chandelles.c]]) {
      if (tab[idx] != null) ligne('#b8b8bf', f(tab[idx]), nom);
    }
  }
  series.forEach((s, i) => {
    const v = s.infobulle ? s.infobulle[idx] : u.data[i + 1]?.[idx];
    if (v == null || s.cache) return;
    ligne(couleur(s.couleur), (s.format ?? formatY)(v), s.nom, s.type);
  });
  bulle.style.display = 'block';
  const largeur = bulle.offsetWidth;
  const gauche = u.cursor.left + 14 + largeur > u.over.clientWidth ? u.cursor.left - largeur - 14 : u.cursor.left + 14;
  bulle.style.left = `${Math.max(0, gauche)}px`;
  bulle.style.top = `${Math.max(0, Math.min(u.cursor.top - 10, u.over.clientHeight - bulle.offsetHeight))}px`;
}

export default function Courbes({
  x,
  series,
  hauteur = 220,
  temps = false,
  log = false,
  formatY = v => String(v),
  formatX,
  formatAxeY,
  references = [],
  bandes = [],
  marqueurs = [],
  groupe,
  chandelles,
  trades,
  yMin,
  yMax
}) {
  const conteneur = useRef(null);
  const graphique = useRef(null);
  const props = useRef(null);
  props.current = { series, formatX, formatY, references, bandes, marqueurs, chandelles, trades, yMin, yMax };
  const structure = `${series.map(s => `${s.nom}|${s.type}|${s.couleur}|${s.trait}|${s.remplissage}|${s.sur}`).join(';')}|${temps}|${log}|${groupe}|${hauteur}|${!!chandelles}`;

  useLayoutEffect(() => {
    const el = conteneur.current;
    const bulle = document.createElement('div'); // avant uPlot : il place son curseur des sa creation
    bulle.className = 'infobulle';
    const axe = {
      stroke: MUET,
      grid: { stroke: GRILLE, width: 1 },
      ticks: { stroke: AXE, width: 1, size: 4 },
      font: '11px system-ui, sans-serif',
      gap: 6
    };
    const options = {
      width: Math.max(200, el.clientWidth),
      height: hauteur,
      padding: [10, 10, 0, 0],
      legend: { show: false },
      tzDate: temps ? utc : undefined,
      fmtDate,
      cursor: {
        sync: groupe ? { key: groupe } : undefined,
        drag: { x: true, y: false, setScale: true },
        points: { size: 8, width: 2, stroke: SURFACE }
      },
      scales: {
        x: { time: temps },
        y: {
          distr: log ? 3 : 1,
          log: 10,
          range: (u, min, max) => {
            const p = props.current;
            let bas = min;
            let haut = max;
            if (p.chandelles) {
              const [a, b] = bornesVisibles(u);
              bas = Infinity;
              haut = -Infinity;
              for (let i = a; i <= b; i++) {
                if (p.chandelles.l[i] != null) bas = Math.min(bas, p.chandelles.l[i]);
                if (p.chandelles.h[i] != null) haut = Math.max(haut, p.chandelles.h[i]);
              }
              for (const s of p.series) {
                for (let i = a; i <= b; i++) {
                  const v = s.valeurs[i];
                  if (v != null && s.dansEchelle !== false) {
                    bas = Math.min(bas, v);
                    haut = Math.max(haut, v);
                  }
                }
              }
              if (!Number.isFinite(bas)) return [0, 1];
            }
            if (p.yMin != null) bas = Math.min(bas, p.yMin);
            if (p.yMax != null) haut = Math.max(haut, p.yMax);
            if (log) return uPlot.rangeLog(bas > 0 ? bas : 1e-6, haut > 0 ? haut : 1, 10, true);
            if (bas === haut) return [bas - 1, haut + 1];
            const marge = (haut - bas) * 0.06;
            return [p.yMin != null && p.yMin === bas ? bas : bas - marge, p.yMax != null && p.yMax === haut ? haut : haut + marge];
          }
        }
      },
      axes: [
        // Hors du temps, l'abscisse compte des generations : des graduations entieres seulement.
        temps ? { ...axe, values: VALEURS_TEMPS } : { ...axe, incrs: [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000] },
        // uPlot passe null pour les graduations qu'il masque faute de place (echelle logarithmique) : pas d'etiquette.
        { ...axe, size: 58, values: (u, valeurs) => valeurs.map(v => (v == null ? null : (formatAxeY ?? props.current.formatY)(v))) }
      ],
      // Remplissage entre deux series : celle du dessus porte remplissage, et sur, l'indice de celle du dessous.
      bands: series.flatMap((s, i) => (s.sur != null ? [{ series: [i + 1, s.sur + 1] }] : [])),
      series: [
        {},
        ...series.map(s => {
          const teinte = couleur(s.couleur);
          return {
            label: s.nom,
            stroke: s.cache ? 'transparent' : s.trait ? couleur(s.trait) : teinte,
            width: s.cache ? 0 : s.largeur ?? 2,
            fill: s.type === 'aire' ? avecAlpha(teinte, 0.1) : s.remplissage ? couleur(s.remplissage) : undefined,
            paths: s.type === 'points' || s.cache ? () => null : s.type === 'marches' ? uPlot.paths.stepped({ align: 1 }) : undefined,
            points: s.type === 'points' ? { show: true, size: 7, width: 2, stroke: SURFACE, fill: teinte } : { show: false },
            spanGaps: false
          };
        })
      ],
      hooks: {
        drawClear: [u => dessinerBandes(u, props.current.bandes)],
        drawAxes: [u => props.current.chandelles && dessinerChandelles(u, props.current.chandelles)],
        draw: [
          u => {
            dessinerReperes(u, props.current.references, props.current.marqueurs);
            if (props.current.trades) dessinerTrades(u, props.current.trades);
          }
        ],
        setCursor: [u => remplirInfobulle(u, bulle, props)],
        setScale: [
          (u, cle) => {
            if (cle !== 'x' || !groupe || u._synchro) return;
            for (const autre of zooms.get(groupe) ?? []) {
              if (autre === u) continue;
              autre._synchro = true;
              autre.setScale('x', { min: u.scales.x.min, max: u.scales.x.max });
              autre._synchro = false;
            }
          }
        ]
      }
    };
    const donnees = [x, ...series.map(s => s.valeurs)];
    const u = new uPlot(options, donnees, el);
    u.over.appendChild(bulle);
    u.over.addEventListener('mouseleave', () => (bulle.style.display = 'none'));
    graphique.current = u;
    if (groupe) {
      if (!zooms.has(groupe)) zooms.set(groupe, new Set());
      zooms.get(groupe).add(u);
    }
    const observateur = new ResizeObserver(() => {
      const largeur = Math.max(200, el.clientWidth);
      if (largeur !== u.width) u.setSize({ width: largeur, height: hauteur });
    });
    observateur.observe(el);
    return () => {
      observateur.disconnect();
      zooms.get(groupe)?.delete(u);
      u.destroy();
      graphique.current = null;
    };
  }, [structure]); // eslint-disable-line react-hooks/exhaustive-deps

  // Nouvelles donnees sans recreer le graphique : le zoom en cours est garde s'il y en a un.
  useEffect(() => {
    const u = graphique.current;
    if (!u) return;
    const zoome = u.scales.x.min != null && u.data[0].length && (u.scales.x.min > u.data[0][0] || u.scales.x.max < u.data[0][u.data[0].length - 1]);
    const avant = zoome ? { min: u.scales.x.min, max: u.scales.x.max } : null;
    u.setData([x, ...series.map(s => s.valeurs)], !zoome);
    if (avant) u.setScale('x', avant);
  }, [x, series]);

  useEffect(() => {
    graphique.current?.redraw(false);
  }, [references, bandes, marqueurs, chandelles, trades]);

  return <div className="graphique" ref={conteneur} style={{ minHeight: hauteur }} />;
}
