// ColorBends de React Bits (reactbits.dev/backgrounds/color-bends). L'original tourne sur three.js : ici le meme
// shader tourne sur ogl, deja present, par le socle commun (toile.js), pour ne pas ajouter de dependance. Seules
// les declarations que three.js ajoute d'office (precision, attributs) sont ecrites a la main.
import { useEffect, useRef } from 'react';
import { lancerToile, rgb } from '../toile.js';
import './ColorBends.css';

const MAX_COLORS = 8;

const frag = `
precision highp float;
#define MAX_COLORS ${MAX_COLORS}
uniform vec2 uCanvas;
uniform float uTime;
uniform float uSpeed;
uniform vec2 uRot;
uniform int uColorCount;
uniform vec3 uColors[MAX_COLORS];
uniform int uTransparent;
uniform float uScale;
uniform float uFrequency;
uniform float uWarpStrength;
uniform vec2 uPointer; // in NDC [-1,1]
uniform float uMouseInfluence;
uniform float uParallax;
uniform float uNoise;
uniform int uIterations;
uniform float uIntensity;
uniform float uBandWidth;
varying vec2 vUv;

void main() {
  float t = uTime * uSpeed;
  vec2 p = vUv * 2.0 - 1.0;
  p += uPointer * uParallax * 0.1;
  vec2 rp = vec2(p.x * uRot.x - p.y * uRot.y, p.x * uRot.y + p.y * uRot.x);
  vec2 q = vec2(rp.x * (uCanvas.x / uCanvas.y), rp.y);
  q /= max(uScale, 0.0001);
  q /= 0.5 + 0.2 * dot(q, q);
  q += 0.2 * cos(t) - 7.56;
  vec2 toward = (uPointer - rp);
  q += toward * uMouseInfluence * 0.2;

    for (int j = 0; j < 5; j++) {
      if (j >= uIterations - 1) break;
      vec2 rr = sin(1.5 * (q.yx * uFrequency) + 2.0 * cos(q * uFrequency));
      q += (rr - q) * 0.15;
    }

    vec3 col = vec3(0.0);
    float a = 1.0;

    if (uColorCount > 0) {
      vec2 s = q;
      vec3 sumCol = vec3(0.0);
      float cover = 0.0;
      for (int i = 0; i < MAX_COLORS; ++i) {
            if (i >= uColorCount) break;
            s -= 0.01;
            vec2 r = sin(1.5 * (s.yx * uFrequency) + 2.0 * cos(s * uFrequency));
            float m0 = length(r + sin(5.0 * r.y * uFrequency - 3.0 * t + float(i)) / 4.0);
            float kBelow = clamp(uWarpStrength, 0.0, 1.0);
            float kMix = pow(kBelow, 0.3); // strong response across 0..1
            float gain = 1.0 + max(uWarpStrength - 1.0, 0.0); // allow >1 to amplify displacement
            vec2 disp = (r - s) * kBelow;
            vec2 warped = s + disp * gain;
            float m1 = length(warped + sin(5.0 * warped.y * uFrequency - 3.0 * t + float(i)) / 4.0);
            float m = mix(m0, m1, kMix);
            float w = 1.0 - exp(-uBandWidth / exp(uBandWidth * m));
            sumCol += uColors[i] * w;
            cover = max(cover, w);
      }
      col = clamp(sumCol, 0.0, 1.0);
      a = uTransparent > 0 ? cover : 1.0;
    } else {
        vec2 s = q;
        for (int k = 0; k < 3; ++k) {
            s -= 0.01;
            vec2 r = sin(1.5 * (s.yx * uFrequency) + 2.0 * cos(s * uFrequency));
            float m0 = length(r + sin(5.0 * r.y * uFrequency - 3.0 * t + float(k)) / 4.0);
            float kBelow = clamp(uWarpStrength, 0.0, 1.0);
            float kMix = pow(kBelow, 0.3);
            float gain = 1.0 + max(uWarpStrength - 1.0, 0.0);
            vec2 disp = (r - s) * kBelow;
            vec2 warped = s + disp * gain;
            float m1 = length(warped + sin(5.0 * warped.y * uFrequency - 3.0 * t + float(k)) / 4.0);
            float m = mix(m0, m1, kMix);
            col[k] = 1.0 - exp(-uBandWidth / exp(uBandWidth * m));
        }
        a = uTransparent > 0 ? max(max(col.r, col.g), col.b) : 1.0;
    }

    col *= uIntensity;

    if (uNoise > 0.0001) {
      float n = fract(sin(dot(gl_FragCoord.xy + vec2(uTime), vec2(12.9898, 78.233))) * 43758.5453123);
      col += (n - 0.5) * uNoise;
      col = clamp(col, 0.0, 1.0);
    }

    vec3 rgb = (uTransparent > 0) ? col * a : col;
    gl_FragColor = vec4(rgb, a);
}
`;

const vert = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

export default function ColorBends({
  className = '',
  style,
  rotation = 90,
  speed = 0.2,
  colors = [],
  transparent = true,
  autoRotate = 0,
  scale = 1,
  frequency = 1,
  warpStrength = 1,
  mouseInfluence = 1,
  parallax = 0.5,
  noise = 0.15,
  iterations = 1,
  intensity = 1.5,
  bandWidth = 6,
  dpr = 1
}) {
  const conteneur = useRef(null);
  const reglages = useRef(null);
  reglages.current = { rotation, speed, colors, transparent, autoRotate, scale, frequency, warpStrength, mouseInfluence, parallax, noise, iterations, intensity, bandWidth };

  useEffect(() => {
    const pointeur = [0, 0];
    const t = lancerToile(conteneur.current, {
      vertex: vert,
      fragment: frag,
      dpr,
      alpha: true,
      premultipliedAlpha: true,
      webgl: 1,
      pointeur: true,
      uniforms: {
        uCanvas: { value: [1, 1] },
        uTime: { value: 0 },
        uSpeed: { value: 0.2 },
        uRot: { value: [1, 0] },
        uColorCount: { value: 0 },
        uColors: { value: Array.from({ length: MAX_COLORS }, () => [0, 0, 0]) },
        uTransparent: { value: 1 },
        uScale: { value: 1 },
        uFrequency: { value: 1 },
        uWarpStrength: { value: 1 },
        uPointer: { value: pointeur },
        uMouseInfluence: { value: 1 },
        uParallax: { value: 0.5 },
        uNoise: { value: 0.15 },
        uIterations: { value: 1 },
        uIntensity: { value: 1.5 },
        uBandWidth: { value: 6 }
      },
      surTaille: (e, p) => (p.uniforms.uCanvas.value = [e.largeur, e.hauteur]),
      avantRendu: ({ temps, dt, souris, program }) => {
        const r = reglages.current;
        const u = program.uniforms;
        const deg = (r.rotation % 360) + r.autoRotate * temps;
        const rad = (deg * Math.PI) / 180;
        u.uRot.value = [Math.cos(rad), Math.sin(rad)];
        const cible = souris.depuis > 0 ? [Math.max(-1, Math.min(1, souris.x * 2 - 1)), Math.max(-1, Math.min(1, -(souris.y * 2 - 1)))] : [0, 0];
        const k = Math.min(1, dt * 8);
        pointeur[0] += (cible[0] - pointeur[0]) * k;
        pointeur[1] += (cible[1] - pointeur[1]) * k;
        const liste = (r.colors || []).filter(Boolean).slice(0, MAX_COLORS);
        u.uColors.value = Array.from({ length: MAX_COLORS }, (_, i) => (i < liste.length ? rgb(liste[i]) : [0, 0, 0]));
        u.uColorCount.value = liste.length;
        u.uTime.value = temps;
        u.uSpeed.value = r.speed;
        u.uTransparent.value = r.transparent ? 1 : 0;
        u.uScale.value = r.scale;
        u.uFrequency.value = r.frequency;
        u.uWarpStrength.value = r.warpStrength;
        u.uMouseInfluence.value = r.mouseInfluence;
        u.uParallax.value = r.parallax;
        u.uNoise.value = r.noise;
        u.uIterations.value = r.iterations;
        u.uIntensity.value = r.intensity;
        u.uBandWidth.value = r.bandWidth;
      }
    });
    return () => t.arreter();
  }, [dpr]);

  return <div ref={conteneur} className={`color-bends-container ${className}`} style={style} />;
}
