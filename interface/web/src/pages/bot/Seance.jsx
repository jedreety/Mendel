// La seance de test : le benchmark rejoue comme un film. Le marche defile en accelere jusqu'a chaque trade du
// bot, ralentit, montre le trade vivre jusqu'a sa cloture, puis repart vers le suivant ; le portefeuille et
// l'historique des trades suivent en temps reel. A la fin, le graphique recule pour montrer tout le bloc de
// test, et le portefeuille du bot se lit a cote de celui du bot tire au hasard, jamais entraine.
// Le benchmark fait partir chaque trimestre du capital initial ; ici chacun repart de ce que le precedent a
// laisse, comme le rendement chaine du verdict. Les resultats des trades suivent la meme echelle.
import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { enc, lire } from '../../api.js';
import { argent, decimal, jourHeure, nombre, pctSigne, signe } from '../../format.js';
import { Carte, EnTeteCarte, Icone, Message } from '../../composants/Base.jsx';
import { avecAlpha, couleur } from '../../graphiques/Courbes.jsx';
import { preparerTrades } from './Trades.jsx';

const HEURE = 3600;
const HAUT_MARCHE = 340;
const HAUT_PORTEFEUILLE = 190;
const MARGE = { gauche: 64, droite: 16, haut: 14, bas: 26 };
const POLICE = '11px "Segoe UI", system-ui, sans-serif';
const POLICE_FORTE = '600 11.5px "Segoe UI", system-ui, sans-serif';
const ZOOM_S = 1.4;
const PAS_HEURES = [1, 2, 3, 6, 12, 24, 48, 168, 336];
const jourMois = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', day: 'numeric', month: 'short' });
const moisCourt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'UTC', month: 'short' });

const sortie = u => 1 - (1 - u) ** 3; // ease-out : vite au depart, lent a l'arrivee
const douce = u => (u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2);
const enDouceur = u => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2);
const borne = (v, a, b) => Math.max(a, Math.min(b, v));
const lisser = (dt, tau) => 1 - Math.exp(-dt / tau);
const iso = s => new Date(s * 1000).toISOString();

function lireRejeu(nom, sous, trimestre) {
  return lire(`/api/runs/${enc(nom)}/rejeu/benchmark/${enc(sous)}/${enc(trimestre)}`);
}

// --- Donnees ---

// Valeur d'une serie horaire a une position fractionnaire : entre deux barres, en ligne droite.
function valeurA(tab, h) {
  const i = Math.floor(h);
  if (i < 0) return tab[0];
  if (i >= tab.length - 1) return tab[tab.length - 1];
  return tab[i] + (tab[i + 1] - tab[i]) * (h - i);
}

// Position d'un instant en barres depuis la premiere, fractionnaire entre deux barres.
function positionDe(temps, t) {
  let a = 0;
  let b = temps.length - 1;
  if (t <= temps[a]) return a;
  if (t >= temps[b]) return b;
  while (b - a > 1) {
    const m = (a + b) >> 1;
    if (temps[m] <= t) a = m;
    else b = m;
  }
  return a + (t - temps[a]) / (temps[b] - temps[a]);
}

// Trimestres bout a bout, sans leur prechauffage : chacun repart de ce que le precedent a laisse.
function enchainer(rejeux) {
  const temps = [];
  const capital = [];
  const stop = [];
  const cible = [];
  const trades = [];
  const debuts = [];
  let facteur = 1;
  rejeux.forEach((r, q) => {
    const d = r.prechauffage;
    debuts.push(temps.length);
    for (let i = d; i < r.temps.length; i++) {
      temps.push(r.temps[i]);
      capital.push(facteur * Number(r.capital[i]));
      stop.push(r.caps.stop[i] == null ? null : Number(r.caps.stop[i]));
      cible.push(r.caps.cible[i] == null ? null : Number(r.caps.cible[i]));
    }
    for (const t of preparerTrades(r)) if (t.entree >= r.temps[d]) trades.push({ ...t, net: t.net * facteur, frais: t.frais * facteur, trimestre: q });
    facteur *= Number(r.capital[r.capital.length - 1]) / Number(r.resume.capital_initial);
  });
  return { temps, capital, stop, cible, trades, debuts };
}

function preparer(bot, hasard, barres) {
  const b = enchainer(bot);
  const n = b.temps.length;
  const capital0 = Number(bot[0].resume.capital_initial);
  const parOuverture = new Map(barres.map(x => [x[0], x]));
  const [o, h, l, c] = [0, 1, 2, 3].map(() => new Float64Array(n).fill(NaN));
  b.temps.forEach((t, i) => {
    const x = parOuverture.get(t - HEURE);
    if (x) [o[i], h[i], l[i], c[i]] = [Number(x[1]), Number(x[2]), Number(x[3]), Number(x[4])];
  });
  let autre = null;
  if (hasard) {
    const a = enchainer(hasard);
    const parTemps = new Map(a.temps.map((t, i) => [t, a.capital[i]]));
    autre = Float64Array.from(b.temps, t => parTemps.get(t) ?? NaN);
  }
  const trades = b.trades.map(t => {
    const e = positionDe(b.temps, t.entree);
    const i = Math.round(e);
    return { ...t, e, s: positionDe(b.temps, t.sortie), avant: i >= 1 ? b.capital[i - 1] : capital0 };
  });
  // Barres tenues par un trade, de celle qui suit l'entree a celle de la sortie.
  const couvert = new Int32Array(n).fill(-1);
  trades.forEach((t, k) => {
    for (let i = Math.floor(t.e) + 1; i <= Math.min(n - 1, Math.ceil(t.s)); i++) couvert[i] = k;
  });
  // Plus bas et plus haut des deux portefeuilles depuis le debut, pour l'echelle qui suit la lecture.
  const pmin = new Float64Array(n);
  const pmax = new Float64Array(n);
  let mi = capital0;
  let ma = capital0;
  for (let i = 0; i < n; i++) {
    for (const v of [b.capital[i], autre?.[i]]) {
      if (Number.isFinite(v)) {
        mi = Math.min(mi, v);
        ma = Math.max(ma, v);
      }
    }
    pmin[i] = mi;
    pmax[i] = ma;
  }
  let bas = Infinity;
  let haut = -Infinity;
  for (let i = 0; i < n; i++) {
    if (l[i] < bas) bas = l[i];
    if (h[i] > haut) haut = h[i];
  }
  if (!Number.isFinite(bas)) [bas, haut] = [0, 1];
  const mp = (haut - bas) * 0.06;
  const mf = Math.max((ma - mi) * 0.12, capital0 * 0.002);
  const complet = { gauche: -0.5, droite: n - 0.5, ymin: bas - mp, ymax: haut + mp, pmin: mi - mf, pmax: ma + mf };
  return { n, temps: b.temps, o, h, l, c, capital: b.capital, stop: b.stop, cible: b.cible, trades, couvert, debuts: b.debuts, capital0, hasard: autre, pmin, pmax, complet };
}

// --- Scenario : approche en ease-out, trade, courte pause a la cloture ---

function scenario(trades, n) {
  // L'ouverture du marche, puis une premiere approche assez lente pour qu'on la voie : hors compression.
  const segments = [{ genre: 'ouverture', de: 0, a: 0, duree: 0.9, fixe: true }];
  let h = 0;
  const approche = a => {
    const fixe = segments.length === 1;
    if (a - h > 0.01) segments.push({ genre: 'approche', de: h, a, duree: fixe ? 1.4 : Math.min(1.6, 0.25 + 0.07 * Math.sqrt(a - h)), fixe });
    h = Math.max(h, a);
  };
  trades.forEach((t, k) => {
    approche(t.e);
    segments.push({ genre: 'trade', de: h, a: Math.max(h, t.s), k, duree: Math.min(2.4, 0.45 + 0.16 * Math.sqrt(Math.max(1, t.s - t.e))) });
    h = Math.max(h, t.s);
    segments.push({ genre: 'pause', de: h, a: h, k, duree: 0.35 });
  });
  approche(n - 1);
  // Moins d'une minute quel que soit le nombre de trades : les approches se compriment les premieres.
  const fixes = segments.filter(s => s.fixe).reduce((x, s) => x + s.duree, 0);
  const budget = borne(15 + 0.4 * trades.length, 18, 50) - fixes;
  const somme = genre => segments.filter(s => s.genre === genre && !s.fixe).reduce((x, s) => x + s.duree, 0);
  const [A, T, P] = ['approche', 'trade', 'pause'].map(somme);
  if (A + T + P > budget) {
    const fa = Math.min(1, (budget * 0.35) / (A || 1));
    const fp = Math.min(1, (budget * 0.1) / (P || 1));
    const ft = Math.min(1, Math.max(0, budget - A * fa - P * fp) / (T || 1));
    for (const s of segments) if (!s.fixe) s.duree *= s.genre === 'approche' ? fa : s.genre === 'pause' ? fp : ft;
  }
  let t = 0;
  for (const s of segments) {
    s.debut = t;
    t += s.duree;
  }
  return { segments, total: t, intro: fixes };
}

function etatInitial(d, lecture, sc) {
  if (!lecture) return { phase: 'fin', h: d.n - 1, tau: 0, iseg: 0, fermes: d.trades.length - 1, ouvert: null, effets: [], horloge: 0, intro: 0, largeur: d.n, ...d.complet };
  return { phase: 'lecture', h: 0, tau: 0, iseg: 0, fermes: -1, ouvert: null, effets: [], horloge: 0, intro: sc.intro, largeur: 96, gauche: -1, droite: 95, ymin: null, ymax: null, pmin: null, pmax: null };
}

function demarrerZoom(e, duree) {
  e.phase = 'zoom';
  e.zoom = { t: 0, duree, de: { gauche: e.gauche, droite: e.droite, ymin: e.ymin, ymax: e.ymax, pmin: e.pmin, pmax: e.pmax } };
}

// Echelle des prix sur toute la fenetre visible, heures a venir comprises : pendant une approche rapide, le
// cours ne sort pas du cadre avant que l'echelle ait suivi.
function bornesPrix(d, gauche, droite, h, ouvert) {
  const a = Math.max(0, Math.floor(gauche));
  const b = Math.min(d.n - 1, Math.ceil(droite));
  let bas = Infinity;
  let haut = -Infinity;
  for (let i = a; i <= b; i++) {
    if (d.l[i] < bas) bas = d.l[i];
    if (d.h[i] > haut) haut = d.h[i];
  }
  if (ouvert != null) {
    const t = d.trades[ouvert];
    const i = Math.min(d.n - 1, Math.floor(h));
    for (const v of [t.prixEntree, d.stop[i], d.cible[i]]) {
      if (v != null) {
        bas = Math.min(bas, v);
        haut = Math.max(haut, v);
      }
    }
  }
  if (!Number.isFinite(bas)) return [d.complet.ymin, d.complet.ymax];
  const marge = Math.max((haut - bas) * 0.14, haut * 0.001);
  return [bas - marge, haut + marge];
}

function bornesPortefeuille(d, h) {
  const i = borne(Math.ceil(h), 0, d.n - 1);
  const marge = Math.max((d.pmax[i] - d.pmin[i]) * 0.15, d.capital0 * 0.002);
  return [d.pmin[i] - marge, d.pmax[i] + marge];
}

// Trades fermes et trade ouvert a la position de lecture ; un trade qui se ferme lance son effet.
function reveler(e, d) {
  while (e.fermes + 1 < d.trades.length && d.trades[e.fermes + 1].s <= e.h + 1e-9) {
    e.fermes += 1;
    e.effets.push({ k: e.fermes, debut: e.horloge });
  }
  const t = d.trades[e.fermes + 1];
  e.ouvert = t && t.e <= e.h ? e.fermes + 1 : null;
}

function avancer(e, dt, d, sc) {
  e.horloge += dt;
  e.effets = e.effets.filter(f => e.horloge - f.debut < 1.2);
  if (e.phase === 'lecture') {
    e.tau += dt;
    const segs = sc.segments;
    while (e.iseg < segs.length && e.tau >= segs[e.iseg].debut + segs[e.iseg].duree) e.iseg += 1;
    const s = segs[e.iseg];
    if (s) {
      const u = s.duree > 0 ? borne((e.tau - s.debut) / s.duree, 0, 1) : 1;
      e.h = s.de + (s.a - s.de) * (s.genre === 'approche' ? sortie(u) : s.genre === 'trade' ? douce(u) : 1);
    } else e.h = d.n - 1;
    reveler(e, d);
    // Camera : la tete de lecture a droite ; resserree sur un trade, plus large entre deux.
    let cible = e.largeur;
    if (s?.genre === 'approche') cible = borne((s.a - s.de) * 0.9, 72, 240);
    else if (s?.k != null) cible = borne((d.trades[s.k].s - d.trades[s.k].e) * 2.4, 48, 240);
    e.largeur += (cible - e.largeur) * lisser(dt, 0.35);
    e.droite = e.h + 0.2 * e.largeur;
    e.gauche = e.droite - e.largeur;
    if (e.gauche < -1) {
      e.gauche = -1;
      e.droite = e.gauche + e.largeur;
    }
    const [bas, haut] = bornesPrix(d, e.gauche, e.droite, e.h, e.ouvert);
    const [pbas, phaut] = bornesPortefeuille(d, e.h);
    // Le portefeuille suit plus vite : une grosse perte ne doit pas sortir du cadre, meme un instant.
    const k = lisser(dt, 0.15);
    const kp = lisser(dt, 0.06);
    e.ymin = e.ymin == null ? bas : e.ymin + (bas - e.ymin) * k;
    e.ymax = e.ymax == null ? haut : e.ymax + (haut - e.ymax) * k;
    e.pmin = e.pmin == null ? pbas : e.pmin + (pbas - e.pmin) * kp;
    e.pmax = e.pmax == null ? phaut : e.pmax + (phaut - e.pmax) * kp;
    if (!s) demarrerZoom(e, ZOOM_S);
  } else if (e.phase === 'zoom') {
    e.zoom.t += dt;
    const u = enDouceur(borne(e.zoom.t / e.zoom.duree, 0, 1));
    for (const cle of ['gauche', 'droite', 'ymin', 'ymax', 'pmin', 'pmax']) e[cle] = e.zoom.de[cle] + (d.complet[cle] - e.zoom.de[cle]) * u;
    if (e.zoom.t >= e.zoom.duree) e.phase = 'fin';
  }
}

// --- Dessin ---

function graduations(min, max, cible = 4) {
  const brut = (max - min) / cible;
  if (!(brut > 0)) return [];
  const p = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 5, 10].map(m => m * p).find(s => s >= brut);
  const decimales = Math.max(0, -Math.floor(Math.log10(pas)));
  const liste = [];
  for (let v = Math.ceil(min / pas) * pas; v <= max; v += pas) liste.push({ v, texte: decimal(v, decimales) });
  return liste;
}

// Graduations du temps : heures, jours ou semaines selon la place, sinon mois.
function graduationsTemps(t0, t1, largeur) {
  const duree = Math.max(1, t1 - t0);
  const pas = PAS_HEURES.find(p => ((p * HEURE) / duree) * largeur >= 84);
  const liste = [];
  if (pas) {
    const s = pas * HEURE;
    for (let t = Math.ceil(t0 / s) * s; t <= t1; t += s) {
      const date = new Date(t * 1000);
      liste.push({ t, texte: pas < 24 && t % 86400 ? `${String(date.getUTCHours()).padStart(2, '0')}:00` : jourMois.format(date) });
    }
    return liste;
  }
  const saut = ((31 * 86400) / duree) * largeur >= 84 ? 1 : 3;
  const debut = new Date(t0 * 1000);
  let m = debut.getUTCMonth() + 1;
  while (m % saut) m += 1;
  for (;;) {
    const t = Date.UTC(debut.getUTCFullYear(), m, 1) / 1000;
    if (t > t1) break;
    const date = new Date(t * 1000);
    liste.push({ t, texte: date.getUTCMonth() ? moisCourt.format(date) : `${moisCourt.format(date)} ${date.getUTCFullYear()}` });
    m += saut;
  }
  return liste;
}

function preparerToile(toile) {
  const r = window.devicePixelRatio || 1;
  const L = toile.width / r;
  const H = toile.height / r;
  const ctx = toile.getContext('2d');
  ctx.setTransform(r, 0, 0, r, 0, 0);
  ctx.clearRect(0, 0, L, H);
  return { ctx, L, x0: MARGE.gauche, y0: MARGE.haut, w: L - MARGE.gauche - MARGE.droite, h: H - MARGE.haut - MARGE.bas };
}

function grille(g, Y, min, max, coul) {
  const { ctx } = g;
  ctx.font = POLICE;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 1;
  for (const v of graduations(min, max)) {
    const y = Math.round(Y(v.v)) + 0.5;
    ctx.strokeStyle = coul.grille;
    ctx.beginPath();
    ctx.moveTo(g.x0, y);
    ctx.lineTo(g.x0 + g.w, y);
    ctx.stroke();
    ctx.fillStyle = coul.muet;
    ctx.fillText(v.texte, g.x0 - 8, y);
  }
}

function axeTemps(g, d, X, gauche, droite, coul) {
  const { ctx } = g;
  const t0 = d.temps[0];
  ctx.strokeStyle = coul.axe;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(g.x0, g.y0 + g.h + 0.5);
  ctx.lineTo(g.x0 + g.w, g.y0 + g.h + 0.5);
  ctx.stroke();
  ctx.font = POLICE;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillStyle = coul.muet;
  for (const tick of graduationsTemps(t0 + gauche * HEURE, t0 + droite * HEURE, g.w)) {
    if (tick.t < t0 || tick.t > d.temps[d.n - 1]) continue;
    const x = Math.round(X((tick.t - t0) / HEURE)) + 0.5;
    if (x < g.x0 || x > g.x0 + g.w) continue;
    ctx.beginPath();
    ctx.moveTo(x, g.y0 + g.h);
    ctx.lineTo(x, g.y0 + g.h + 4);
    ctx.stroke();
    ctx.fillText(tick.texte, x, g.y0 + g.h + 7);
  }
}

function trimestres(g, d, X, tete, coul, libelles) {
  const { ctx } = g;
  ctx.font = POLICE;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.lineWidth = 1;
  d.debuts.forEach((i, q) => {
    if (!q || i - 0.5 > tete) return;
    const x = Math.round(X(i - 0.5)) + 0.5;
    ctx.strokeStyle = coul.bord;
    ctx.beginPath();
    ctx.moveTo(x, g.y0);
    ctx.lineTo(x, g.y0 + g.h);
    ctx.stroke();
    if (libelles) {
      ctx.fillStyle = coul.muet;
      ctx.fillText(`T${q + 1}`, x + 4, g.y0 + 3);
    }
  });
}

// Achat : triangle sous le cours, a l'encre. Vente : au-dessus, couleur du resultat. Anneau de la surface.
function triangle(ctx, x, y, achat, teinte, surface) {
  const t = 5.5;
  const sens = achat ? 1 : -1;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x - t, y + sens * t * 1.5);
  ctx.lineTo(x + t, y + sens * t * 1.5);
  ctx.closePath();
  ctx.lineWidth = 2;
  ctx.strokeStyle = surface;
  ctx.stroke();
  ctx.fillStyle = teinte;
  ctx.fill();
}

// Pastille : texte blanc sur la couleur du resultat.
function pastille(ctx, x, y, texte, fond, L, centre = false) {
  ctx.font = POLICE_FORTE;
  const w = ctx.measureText(texte).width + 14;
  const px = borne(centre ? x - w / 2 : x, 2, L - w - 2);
  ctx.fillStyle = fond;
  ctx.beginPath();
  ctx.roundRect(px, y - 10, w, 20, 10);
  ctx.fill();
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(texte, px + 7, y + 0.5);
}

function dessinerMarche(toile, d, e, coul, survol) {
  const g = preparerToile(toile);
  const { ctx, x0, y0, w, h } = g;
  const { gauche, droite, ymin, ymax } = e;
  const X = i => x0 + ((i - gauche) / (droite - gauche)) * w;
  const Y = v => y0 + ((ymax - v) / (ymax - ymin)) * h;
  const fin = e.phase === 'fin';
  const tete = fin ? d.n - 1 : e.h;
  const limite = Math.min(d.n - 1, Math.floor(tete));
  const vTete = valeurA(d.capital, tete);
  grille(g, Y, ymin, ymax, coul);
  axeTemps(g, d, X, gauche, droite, coul);

  ctx.save();
  ctx.beginPath();
  ctx.rect(x0, y0, w, h);
  ctx.clip();
  trimestres(g, d, X, tete, coul, true);
  // Periodes tenues, teintees par le resultat ; celle du trade ouvert, par son resultat du moment.
  for (let k = 0; k < d.trades.length && d.trades[k].e <= tete; k++) {
    const t = d.trades[k];
    const ferme = k <= e.fermes;
    const a = X(t.e);
    const b = X(Math.min(t.s, tete));
    if (b < x0 || a > x0 + w) continue;
    ctx.fillStyle = avecAlpha((ferme ? t.gain : vTete >= t.avant) ? coul.gain : coul.perte, ferme ? 0.06 : 0.11);
    ctx.fillRect(a, y0, Math.max(1, b - a), h);
  }
  // Le prix : en retrait, sauf pendant un trade, ou il prend la couleur du resultat.
  const pasPx = w / (droite - gauche);
  const a = Math.max(0, Math.floor(gauche) - 1);
  const b = Math.min(limite, Math.ceil(droite) + 1);
  const teinteBarre = i => {
    const k = d.couvert[i];
    if (k < 0 || d.trades[k].e > tete) return null;
    return d.c[i] >= d.trades[k].prixEntree ? coul.gain : coul.perte;
  };
  ctx.lineWidth = 1;
  if (pasPx >= 4) {
    const larg = borne(pasPx * 0.62, 1.5, 10);
    for (let i = a; i <= b; i++) {
      if (Number.isNaN(d.o[i])) continue;
      const x = X(i);
      const hausse = d.c[i] >= d.o[i];
      const teinte = teinteBarre(i);
      ctx.strokeStyle = teinte ?? (hausse ? '#a3a3ab' : '#b8b8bf');
      ctx.beginPath();
      ctx.moveTo(Math.round(x) + 0.5, Y(d.h[i]));
      ctx.lineTo(Math.round(x) + 0.5, Y(d.l[i]));
      ctx.stroke();
      const yo = Y(d.o[i]);
      const yc = Y(d.c[i]);
      const haut = Math.min(yo, yc);
      const hauteur = Math.max(1, Math.abs(yc - yo));
      if (hausse) {
        ctx.fillStyle = coul.surface;
        ctx.fillRect(x - larg / 2, haut, larg, hauteur);
        ctx.strokeRect(x - larg / 2, haut, larg, hauteur);
      } else {
        ctx.fillStyle = teinte ? avecAlpha(teinte, 0.6) : '#c9c9cf';
        ctx.fillRect(x - larg / 2, haut, larg, hauteur);
      }
    }
  } else {
    const points = [];
    for (let i = a; i <= b; i++) if (!Number.isNaN(d.c[i])) points.push([X(i), Y(d.c[i])]);
    const vc = valeurA(d.c, tete);
    if (!fin && Number.isFinite(vc)) points.push([X(tete), Y(vc)]);
    if (points.length > 1) {
      const degrade = ctx.createLinearGradient(0, y0, 0, y0 + h);
      degrade.addColorStop(0, avecAlpha(coul.muet, 0.12));
      degrade.addColorStop(1, avecAlpha(coul.muet, 0));
      ctx.beginPath();
      points.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.lineTo(points[points.length - 1][0], y0 + h);
      ctx.lineTo(points[0][0], y0 + h);
      ctx.closePath();
      ctx.fillStyle = degrade;
      ctx.fill();
      ctx.beginPath();
      points.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.strokeStyle = '#a3a3ab';
      ctx.lineWidth = 1.25;
      ctx.lineJoin = 'round';
      ctx.stroke();
    }
    ctx.lineWidth = 2;
    for (let i = Math.max(a, 1); i <= b; i++) {
      const teinte = teinteBarre(i);
      if (!teinte || Number.isNaN(d.c[i]) || Number.isNaN(d.c[i - 1])) continue;
      ctx.strokeStyle = teinte;
      ctx.beginPath();
      ctx.moveTo(X(i - 1), Y(d.c[i - 1]));
      ctx.lineTo(X(i), Y(d.c[i]));
      ctx.stroke();
    }
  }
  // Entrees et sorties : un trait de l'achat a la vente, dans la couleur du resultat.
  for (let k = 0; k < d.trades.length && d.trades[k].e <= tete; k++) {
    const t = d.trades[k];
    const xe = X(t.e);
    if (k <= e.fermes) {
      const xs = X(t.s);
      if (xs < x0 - 10 || xe > x0 + w + 10) continue;
      const teinte = t.gain ? coul.gain : coul.perte;
      ctx.strokeStyle = avecAlpha(teinte, 0.75);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(xe, Y(t.prixEntree));
      ctx.lineTo(xs, Y(t.prixSortie));
      ctx.stroke();
      triangle(ctx, xe, Y(t.prixEntree) + 3, true, coul.encre, coul.surface);
      triangle(ctx, xs, Y(t.prixSortie) - 3, false, teinte, coul.surface);
    } else triangle(ctx, xe, Y(t.prixEntree) + 3, true, coul.encre, coul.surface);
  }
  // Le trade ouvert : son prix d'achat, son stop et son objectif du moment.
  const ouvert = !fin && e.ouvert != null ? d.trades[e.ouvert] : null;
  const niveaux = [];
  if (ouvert) {
    const i = Math.min(d.n - 1, Math.floor(tete));
    const xe = X(ouvert.e);
    const xt = X(tete);
    const niveau = (v, teinte, pointilles, libelle) => {
      if (v == null) return;
      const y = Math.round(Y(v)) + 0.5;
      ctx.strokeStyle = teinte;
      ctx.lineWidth = 1;
      ctx.setLineDash(pointilles ? [4, 3] : []);
      ctx.beginPath();
      ctx.moveTo(xe, y);
      ctx.lineTo(xt, y);
      ctx.stroke();
      ctx.setLineDash([]);
      if (libelle) niveaux.push({ y, libelle });
    };
    niveau(ouvert.prixEntree, avecAlpha(coul.encre, 0.55), false, null);
    niveau(d.stop[i], avecAlpha(coul.perte, 0.9), true, 'stop');
    niveau(d.cible[i], avecAlpha(coul.gain, 0.9), true, 'objectif');
  }
  // La tete de lecture.
  const vc = valeurA(d.c, tete);
  if (!fin) {
    const x = X(tete);
    ctx.strokeStyle = avecAlpha(coul.encre, 0.16);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(Math.round(x) + 0.5, y0);
    ctx.lineTo(Math.round(x) + 0.5, y0 + h);
    ctx.stroke();
    if (Number.isFinite(vc)) {
      const pouls = (e.horloge * 1.4) % 1;
      ctx.fillStyle = avecAlpha(coul.encre, 0.2 * (1 - pouls));
      ctx.beginPath();
      ctx.arc(x, Y(vc), 4 + 11 * pouls, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = coul.encre;
      ctx.strokeStyle = coul.surface;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, Y(vc), 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }
  // Cloture : un anneau qui s'ouvre sur la vente.
  for (const f of e.effets) {
    const t = d.trades[f.k];
    const u = Math.min(1, (e.horloge - f.debut) / 0.6);
    if (u >= 1) continue;
    ctx.strokeStyle = avecAlpha(t.gain ? coul.gain : coul.perte, 1 - u);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(X(t.s), Y(t.prixSortie), 6 + 20 * sortie(u), 0, Math.PI * 2);
    ctx.stroke();
  }
  if (fin && survol != null) {
    const x = Math.round(X(survol)) + 0.5;
    ctx.strokeStyle = avecAlpha(coul.encre, 0.35);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y0);
    ctx.lineTo(x, y0 + h);
    ctx.stroke();
    if (Number.isFinite(d.c[survol])) {
      ctx.fillStyle = coul.encre;
      ctx.strokeStyle = coul.surface;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, Y(d.c[survol]), 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }
  ctx.restore();

  // Hors du cadre : resultat du trade ouvert a la tete, libelles des niveaux, resultats qui s'envolent.
  if (ouvert && Number.isFinite(vc)) {
    const pnl = vTete - ouvert.avant;
    const yp = borne(Y(vc), y0 + 10, y0 + h - 10);
    pastille(ctx, X(tete) + 12, yp, pctSigne(pnl / ouvert.avant, 2), pnl >= 0 ? coul.gain : coul.perte, g.L);
    ctx.font = POLICE;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = coul.muet;
    for (const n of niveaux) if (Math.abs(n.y - yp) > 14 && n.y > y0 && n.y < y0 + h) ctx.fillText(n.libelle, X(tete) + 12, n.y);
  }
  for (const f of e.effets) {
    const age = e.horloge - f.debut;
    const t = d.trades[f.k];
    if (X(t.s) < x0 || X(t.s) > x0 + w) continue;
    ctx.globalAlpha = borne(1 - (age - 0.55) / 0.6, 0, 1);
    pastille(ctx, X(t.s), borne(Y(t.prixSortie) - 24 - 18 * sortie(Math.min(1, age / 1.1)), y0 + 10, y0 + h - 10), pctSigne(t.part, 2), t.gain ? coul.gain : coul.perte, g.L, true);
    ctx.globalAlpha = 1;
  }
  // L'ouverture du marche, le temps de la premiere approche.
  if (e.phase === 'lecture' && e.horloge < e.intro) {
    const debut = new Date(d.temps[0] * 1000);
    const libelle = `Ouverture du marché · ${jourMois.format(debut)} ${debut.getUTCFullYear()}`;
    ctx.globalAlpha = borne((e.intro - e.horloge) / 0.5, 0, 1);
    ctx.font = '600 13px "Segoe UI", system-ui, sans-serif';
    const lt = ctx.measureText(libelle).width + 28;
    const cx = x0 + w / 2;
    const cy = y0 + h / 2;
    ctx.fillStyle = coul.surface;
    ctx.strokeStyle = coul.bord;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(cx - lt / 2, cy - 17, lt, 34, 17);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = coul.encre;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(libelle, cx, cy + 0.5);
    ctx.globalAlpha = 1;
  }
}

function dessinerPortefeuille(toile, d, e, coul, survol) {
  const g = preparerToile(toile);
  const { ctx, x0, y0, w, h } = g;
  const gauche = -0.5;
  const droite = d.n - 0.5;
  const { pmin, pmax } = e;
  const X = i => x0 + ((i - gauche) / (droite - gauche)) * w;
  const Y = v => y0 + ((pmax - v) / (pmax - pmin)) * h;
  const fin = e.phase === 'fin';
  const tete = fin ? d.n - 1 : e.h;
  grille(g, Y, pmin, pmax, coul);
  axeTemps(g, d, X, gauche, droite, coul);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x0, y0, w, h);
  ctx.clip();
  trimestres(g, d, X, d.n, coul, false);
  const yd = Math.round(Y(d.capital0)) + 0.5;
  ctx.strokeStyle = '#bababf';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x0, yd);
  ctx.lineTo(x0 + w, yd);
  ctx.stroke();
  ctx.font = POLICE;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  ctx.fillStyle = coul.muet;
  ctx.fillText('départ', x0 + w - 4, yd + 3);
  const courbe = (tab, teinte) => {
    ctx.beginPath();
    let premier = true;
    for (let i = 0; i <= Math.min(d.n - 1, Math.floor(tete)); i++) {
      if (!Number.isFinite(tab[i])) {
        premier = true;
        continue;
      }
      if (premier) ctx.moveTo(X(i), Y(tab[i]));
      else ctx.lineTo(X(i), Y(tab[i]));
      premier = false;
    }
    const v = valeurA(tab, tete);
    if (!fin && Number.isFinite(v)) ctx.lineTo(X(tete), Y(v));
    ctx.strokeStyle = teinte;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  };
  if (d.hasard) courbe(d.hasard, coul.hasard);
  courbe(d.capital, coul.bot);
  const point = (tab, i, teinte) => {
    const v = valeurA(tab, i);
    if (!Number.isFinite(v)) return;
    ctx.fillStyle = teinte;
    ctx.strokeStyle = coul.surface;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(X(i), Y(v), 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  };
  const repere = fin ? survol : tete;
  if (repere != null) {
    if (fin) {
      const x = Math.round(X(repere)) + 0.5;
      ctx.strokeStyle = avecAlpha(coul.encre, 0.35);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 + h);
      ctx.stroke();
    }
    if (d.hasard) point(d.hasard, repere, coul.hasard);
    point(d.capital, repere, coul.bot);
  }
  ctx.restore();
}

function nomTrimestre(noms, debuts, i) {
  let q = 0;
  while (q + 1 < debuts.length && debuts[q + 1] <= i) q += 1;
  const [an, t] = String(noms[q] ?? '').split('-');
  return t ? `${t.replace('T', 'Trimestre ')} · ${an}` : '';
}

function dureeTrade(t) {
  const h = Math.max(1, Math.round((t.sortie - t.entree) / HEURE));
  return h < 48 ? `${h} h` : `${Math.floor(h / 24)} j ${h % 24} h`;
}

// --- Composant ---

export default function Seance({ nom, trimestres: noms, hasard, cotation = '', decimalesPrix = 2, autoplay = true, onFin }) {
  const reduit = useReducedMotion();
  const cle = noms.join(',');
  const [d, setD] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [phase, setPhase] = useState('chargement');
  const [liste, setListe] = useState({ fermes: -1, ouvert: null });
  const [anime, setAnime] = useState(false);
  const etat = useRef(null);
  const survol = useRef(null);
  const dernier = useRef(liste);
  const finRef = useRef(onFin);
  finRef.current = onFin;
  const toileMarche = useRef(null);
  const toilePortefeuille = useRef(null);
  const dateRef = useRef(null);
  const trimestreRef = useRef(null);
  const valeurRef = useRef(null);
  const variationRef = useRef(null);
  const signeRef = useRef(null);
  const prixRef = useRef(null);
  const botRef = useRef(null);
  const hasardRef = useRef(null);
  const progressionRef = useRef(null);
  const ouvertRef = useRef(null);
  const prix = v => nombre(v, decimalesPrix);
  const couleurs = useMemo(
    () => ({
      gain: couleur('var(--gain)'),
      perte: couleur('var(--perte)'),
      bot: couleur('var(--s1)'),
      hasard: couleur('var(--s2)'),
      encre: couleur('var(--texte)'),
      muet: couleur('var(--texte-3)'),
      bord: couleur('var(--bord-fort)'),
      grille: '#f0f0f2',
      axe: '#dedee3',
      surface: '#ffffff'
    }),
    []
  );
  const sc = useMemo(() => (d ? scenario(d.trades, d.n) : null), [d]);

  useEffect(() => {
    let vivant = true;
    setD(null);
    setErreur(null);
    setPhase('chargement');
    Promise.all([Promise.all(noms.map(q => lireRejeu(nom, 'champion', q))), hasard ? Promise.all(noms.map(q => lireRejeu(nom, hasard, q))) : null])
      .then(async ([bot, autre]) => {
        const premier = bot[0];
        const dernier_ = bot[bot.length - 1];
        const debut = premier.temps[premier.prechauffage] - HEURE;
        const fin = dernier_.temps[dernier_.temps.length - 1];
        const p = await lire(`/api/prix?run=${enc(nom)}&debut=${enc(iso(debut))}&fin=${enc(iso(fin))}`);
        if (vivant) setD(preparer(bot, autre, p.barres));
      })
      .catch(e => {
        if (!vivant) return;
        setErreur(e.message);
        finRef.current?.();
      });
    return () => {
      vivant = false;
    };
  }, [nom, cle, hasard]); // eslint-disable-line react-hooks/exhaustive-deps

  const texte = (ref, valeur) => {
    if (ref.current && ref.current.textContent !== valeur) ref.current.textContent = valeur;
  };

  const dessiner = () => {
    const e = etat.current;
    if (!e || !d) return;
    if (toileMarche.current) dessinerMarche(toileMarche.current, d, e, couleurs, survol.current);
    if (toilePortefeuille.current) dessinerPortefeuille(toilePortefeuille.current, d, e, couleurs, survol.current);
  };

  // Ce qui change a chaque image hors du canvas : la barre du haut, les legendes, le trade ouvert. La liste des
  // trades ne se rafraichit que quand un trade s'ouvre ou se ferme.
  const synchroniser = () => {
    const e = etat.current;
    if (!e || !d) return;
    const h = survol.current ?? (e.phase === 'fin' ? d.n - 1 : e.h);
    const i = borne(Math.floor(h), 0, d.n - 1);
    const v = valeurA(d.capital, h);
    const r = Math.abs(v / d.capital0 - 1) < 5e-5 ? 0 : v / d.capital0 - 1; // pas de « -0,00 % »
    texte(dateRef, `${jourHeure(d.temps[i])} UTC`);
    texte(trimestreRef, nomTrimestre(noms, d.debuts, i));
    texte(valeurRef, argent(v, cotation, 2));
    texte(variationRef, pctSigne(r, 2));
    if (signeRef.current) signeRef.current.className = r > 0 ? 'signe-gain' : r < 0 ? 'signe-perte' : '';
    texte(prixRef, prix(valeurA(d.c, h)));
    texte(botRef, `${argent(v, cotation, 2)} · ${pctSigne(r, 2)}`);
    if (d.hasard) {
      const a = valeurA(d.hasard, h);
      texte(hasardRef, `${argent(a, cotation, 2)} · ${pctSigne(a / d.capital0 - 1, 2)}`);
    }
    if (progressionRef.current) progressionRef.current.style.transform = `scaleX(${e.phase === 'lecture' ? borne(e.tau / sc.total, 0, 1) : 1})`;
    if (e.ouvert != null && ouvertRef.current) {
      const t = d.trades[e.ouvert];
      const pnl = v - t.avant;
      texte(ouvertRef, `${signe(pnl, 2)} ${cotation} · ${pctSigne(pnl / t.avant, 2)}`);
    }
    if (e.fermes !== dernier.current.fermes || e.ouvert !== dernier.current.ouvert) {
      dernier.current = { fermes: e.fermes, ouvert: e.ouvert };
      setListe(dernier.current);
    }
  };

  // Des donnees pretes : la lecture, ou directement la vue d'ensemble.
  useEffect(() => {
    if (!d) return;
    const lecture = autoplay && !reduit;
    etat.current = etatInitial(d, lecture, sc);
    dernier.current = { fermes: etat.current.fermes, ouvert: null };
    setListe(dernier.current);
    setAnime(lecture);
    setPhase(etat.current.phase);
    if (!lecture) finRef.current?.();
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  // Toiles a la taille de leur cadre, en pixels de l'ecran.
  useEffect(() => {
    const ajuster = () => {
      const r = window.devicePixelRatio || 1;
      for (const [toile, hauteur] of [
        [toileMarche.current, HAUT_MARCHE],
        [toilePortefeuille.current, HAUT_PORTEFEUILLE]
      ]) {
        if (!toile) continue;
        const largeur = Math.max(200, toile.parentElement.clientWidth);
        if (toile.width !== Math.round(largeur * r)) toile.width = Math.round(largeur * r);
        if (toile.height !== Math.round(hauteur * r)) toile.height = Math.round(hauteur * r);
      }
      if (etat.current?.phase === 'fin') dessiner();
    };
    ajuster();
    const observateur = new ResizeObserver(ajuster);
    for (const toile of [toileMarche.current, toilePortefeuille.current]) if (toile) observateur.observe(toile.parentElement);
    return () => observateur.disconnect();
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  // La lecture, image par image. Un onglet cache suspend requestAnimationFrame : le pas est borne, la lecture
  // reprend la ou elle en etait.
  useEffect(() => {
    if (!d || (phase !== 'lecture' && phase !== 'zoom')) return;
    let id;
    let avant = performance.now();
    const image = t => {
      const dt = borne((t - avant) / 1000, 0, 0.05);
      avant = t;
      const e = etat.current;
      avancer(e, dt, d, sc);
      dessiner();
      synchroniser();
      if (e.phase !== phase) {
        setPhase(e.phase);
        if (e.phase === 'fin') finRef.current?.();
        return;
      }
      id = requestAnimationFrame(image);
    };
    id = requestAnimationFrame(image);
    return () => cancelAnimationFrame(id);
  }, [d, sc, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (phase !== 'fin') return;
    dessiner();
    synchroniser();
  }, [phase, d]); // eslint-disable-line react-hooks/exhaustive-deps

  const passer = () => {
    const e = etat.current;
    if (!e || e.phase !== 'lecture') return;
    e.h = d.n - 1;
    e.fermes = d.trades.length - 1;
    e.ouvert = null;
    e.effets = [];
    demarrerZoom(e, 0.8);
  };

  const revoir = () => {
    if (!d) return;
    survol.current = null;
    etat.current = etatInitial(d, true, sc);
    dernier.current = { fermes: -1, ouvert: null };
    setListe(dernier.current);
    setAnime(true);
    setPhase('lecture');
  };

  // Survol de la vue d'ensemble : la barre du haut et les legendes donnent l'heure pointee.
  const survoler = (evenement, portefeuille) => {
    const e = etat.current;
    if (!e || !d || e.phase !== 'fin') return;
    const rect = evenement.currentTarget.getBoundingClientRect();
    const [gauche, droite] = portefeuille ? [-0.5, d.n - 0.5] : [e.gauche, e.droite];
    const largeur = rect.width - MARGE.gauche - MARGE.droite;
    const i = Math.round(gauche + ((evenement.clientX - rect.left - MARGE.gauche) / largeur) * (droite - gauche));
    const nouveau = i >= 0 && i < d.n ? i : null;
    if (nouveau === survol.current) return;
    survol.current = nouveau;
    dessiner();
    synchroniser();
  };
  const quitter = () => {
    if (survol.current == null || etat.current?.phase !== 'fin') return;
    survol.current = null;
    dessiner();
    synchroniser();
  };

  const fermes = d ? d.trades.slice(0, liste.fermes + 1).reverse() : [];
  const ouvert = d && liste.ouvert != null ? d.trades[liste.ouvert] : null;
  const enLecture = phase === 'lecture' || phase === 'zoom';

  return (
    <Carte className="seance" titre="La séance de test">
      <EnTeteCarte
        titre="La séance de test"
        description={`Le champion passe ${noms.length} trimestre${noms.length > 1 ? 's' : ''} qu’il n’a jamais vus, une seule fois, sans rien apprendre : il ne fait qu’essayer. Entre deux trades, le marché défile en accéléré.`}
        actions={
          enLecture ? (
            <button type="button" className="bouton petit" onClick={passer} disabled={phase !== 'lecture'}>
              <Icone nom="suivant" taille={13} />
              Passer
            </button>
          ) : phase === 'fin' && !erreur ? (
            <button type="button" className="bouton petit" onClick={revoir}>
              <Icone nom="rafraichir" taille={14} />
              Revoir
            </button>
          ) : null
        }
      />
      {erreur && <Message genre="critique">{erreur}</Message>}
      <div className="seance-hud">
        <div className="seance-hud-bloc">
          <span className="seance-hud-libelle" ref={trimestreRef}>
            Bloc de test
          </span>
          <span className="seance-hud-valeur" ref={dateRef}>
            –
          </span>
        </div>
        <div className="seance-hud-bloc">
          <span className="seance-hud-libelle">Portefeuille</span>
          <span className="seance-hud-valeur seance-hud-grand">
            <span ref={valeurRef}>–</span>
            <small>
              <span ref={signeRef} />
              <span ref={variationRef} />
            </small>
          </span>
        </div>
        <div className="seance-hud-bloc">
          <span className="seance-hud-libelle">Prix</span>
          <span className="seance-hud-valeur" ref={prixRef}>
            –
          </span>
        </div>
      </div>
      <div className="seance-scene">
        <canvas ref={toileMarche} style={{ height: HAUT_MARCHE }} onMouseMove={e => survoler(e, false)} onMouseLeave={quitter} role="img" aria-label="Le marché heure par heure, avec les achats et les ventes du bot" />
        <div className="seance-progression" ref={progressionRef} style={{ opacity: enLecture ? 1 : 0 }} />
        {!d && !erreur && <div className="seance-attente">Préparation de la séance : trades, capital et prix heure par heure…</div>}
      </div>
      <div className="seance-bas">
        <div className="seance-portefeuille">
          <h3>Le portefeuille</h3>
          <div className="seance-legende">
            <span>
              <i className="cle-ligne" style={{ background: 'var(--s1)' }} />
              Votre bot <b ref={botRef} />
            </span>
            {d?.hasard && (
              <span>
                <i className="cle-ligne" style={{ background: 'var(--s2)' }} />
                Bot tiré au hasard, jamais entraîné <b ref={hasardRef} />
              </span>
            )}
          </div>
          <div className="seance-cadre">
            <canvas ref={toilePortefeuille} style={{ height: HAUT_PORTEFEUILLE }} onMouseMove={e => survoler(e, true)} onMouseLeave={quitter} role="img" aria-label="Le portefeuille du bot et celui du bot tiré au hasard, heure par heure" />
          </div>
          <p className="discret">Les trimestres s’enchaînent, gains réinvestis, comme le rendement du verdict.</p>
        </div>
        <div className="seance-journal">
          <h3>
            Ses trades <span className="discret">{d ? `${nombre(liste.fermes + 1)} sur ${nombre(d.trades.length)}` : ''}</span>
          </h3>
          <ul className="seance-historique">
            {ouvert && (
              <li className="seance-trade en-cours">
                <span className="seance-fleche ouvert">
                  <span className="point vivant" />
                </span>
                <span className="seance-trade-texte">
                  <strong>En position</strong>
                  <span>
                    achat à {prix(ouvert.prixEntree)} le {jourHeure(ouvert.entree)}
                  </span>
                </span>
                <span className="seance-trade-cote">
                  <b ref={ouvertRef} />
                  <span>en cours</span>
                </span>
              </li>
            )}
            {fermes.map(t => (
              <motion.li key={t.entree} className="seance-trade" initial={anime ? { opacity: 0, y: -10 } : false} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
                <span className={`seance-fleche ${t.gain ? 'gain' : 'perte'}`} title={t.gain ? 'Trade gagnant' : 'Trade perdant'}>
                  <Icone nom={t.gain ? 'hausse' : 'baisse'} taille={15} epaisseur={2.3} />
                </span>
                <span className="seance-trade-texte">
                  <strong>
                    {signe(t.net, 2)} {cotation}
                    <small>{pctSigne(t.part, 2)}</small>
                  </strong>
                  <span>
                    {prix(t.prixEntree)} → {prix(t.prixSortie)} · {jourHeure(t.entree)}
                  </span>
                </span>
                <span className="seance-trade-cote">
                  <span>{dureeTrade(t)}</span>
                  <span>{t.raison}</span>
                </span>
              </motion.li>
            ))}
            {d && !ouvert && !fermes.length && <li className="discret">{enLecture ? 'Pas encore de trade.' : 'Aucun trade sur le bloc de test.'}</li>}
          </ul>
        </div>
      </div>
    </Carte>
  );
}
