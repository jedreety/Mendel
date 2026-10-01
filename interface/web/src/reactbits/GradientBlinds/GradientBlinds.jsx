// GradientBlinds de React Bits (reactbits.dev/backgrounds/gradient-blinds), shader repris tel quel, mode clair pour
// le fond blanc. Adapte : pose sur le socle commun (toile.js). L'original recreait tout son contexte WebGL quand
// ses couleurs ou sa pause changeaient ; ici, les reglages sont relus a chaque image, sans rien recreer.
import { useEffect, useRef } from 'react';
import { lancerToile, rgb } from '../toile.js';
import './GradientBlinds.css';

const MAX_COLORS = 8;
const prepStops = stops => {
  const base = (stops && stops.length ? stops : ['#FF9FFC', '#5227FF']).slice(0, MAX_COLORS);
  if (base.length === 1) base.push(base[0]);
  while (base.length < MAX_COLORS) base.push(base[base.length - 1]);
  return { arr: base.map(rgb), count: Math.max(2, Math.min(MAX_COLORS, stops?.length ?? 2)) };
};

const vertex = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragment = `
#ifdef GL_ES
precision mediump float;
#endif

uniform vec3  iResolution;
uniform vec2  iMouse;
uniform float iTime;

uniform float uAngle;
uniform float uNoise;
uniform float uBlindCount;
uniform float uSpotlightRadius;
uniform float uSpotlightSoftness;
uniform float uSpotlightOpacity;
uniform float uMirror;
uniform float uDistort;
uniform float uShineFlip;
uniform vec3  uColor0;
uniform vec3  uColor1;
uniform vec3  uColor2;
uniform vec3  uColor3;
uniform vec3  uColor4;
uniform vec3  uColor5;
uniform vec3  uColor6;
uniform vec3  uColor7;
uniform int   uColorCount;
uniform float uLightMode;

varying vec2 vUv;

float rand(vec2 co){
  return fract(sin(dot(co, vec2(12.9898,78.233))) * 43758.5453);
}

vec2 rotate2D(vec2 p, float a){
  float c = cos(a);
  float s = sin(a);
  return mat2(c, -s, s, c) * p;
}

vec3 getGradientColor(float t){
  float tt = clamp(t, 0.0, 1.0);
  int count = uColorCount;
  if (count < 2) count = 2;
  float scaled = tt * float(count - 1);
  float seg = floor(scaled);
  float f = fract(scaled);

  if (seg < 1.0) return mix(uColor0, uColor1, f);
  if (seg < 2.0 && count > 2) return mix(uColor1, uColor2, f);
  if (seg < 3.0 && count > 3) return mix(uColor2, uColor3, f);
  if (seg < 4.0 && count > 4) return mix(uColor3, uColor4, f);
  if (seg < 5.0 && count > 5) return mix(uColor4, uColor5, f);
  if (seg < 6.0 && count > 6) return mix(uColor5, uColor6, f);
  if (seg < 7.0 && count > 7) return mix(uColor6, uColor7, f);
  if (count > 7) return uColor7;
  if (count > 6) return uColor6;
  if (count > 5) return uColor5;
  if (count > 4) return uColor4;
  if (count > 3) return uColor3;
  if (count > 2) return uColor2;
  return uColor1;
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 uv0 = fragCoord.xy / iResolution.xy;

    float aspect = iResolution.x / iResolution.y;
    vec2 p = uv0 * 2.0 - 1.0;
    p.x *= aspect;
    vec2 pr = rotate2D(p, uAngle);
    pr.x /= aspect;
    vec2 uv = pr * 0.5 + 0.5;

    vec2 uvMod = uv;
    if (uDistort > 0.0) {
      float a = uvMod.y * 6.0;
      float b = uvMod.x * 6.0;
      float w = 0.01 * uDistort;
      uvMod.x += sin(a) * w;
      uvMod.y += cos(b) * w;
    }
    float t = uvMod.x;
    if (uMirror > 0.5) {
      t = 1.0 - abs(1.0 - 2.0 * fract(t));
    }
    vec3 base = getGradientColor(t);

    vec2 offset = vec2(iMouse.x/iResolution.x, iMouse.y/iResolution.y);
  float d = length(uv0 - offset);
  float r = max(uSpotlightRadius, 1e-4);
  float dn = d / r;
  float spot = (1.0 - 2.0 * pow(dn, uSpotlightSoftness)) * uSpotlightOpacity;
  vec3 cir = vec3(spot);
  float blindCount = max(uBlindCount, 1.0);
  float stripePhase = uvMod.x * blindCount;
  float stripe = fract(stripePhase);
  float stripeAA = clamp(blindCount * 1.25 / min(iResolution.x, iResolution.y), 0.001, 0.12);
  float edgeDistance = min(stripe, 1.0 - stripe);
  float edgeBlend = 1.0 - smoothstep(0.0, stripeAA, edgeDistance);
  stripe = mix(stripe, 0.5, edgeBlend);
  if (uShineFlip > 0.5) stripe = 1.0 - stripe;
    vec3 ran = vec3(stripe);
    vec3 revealSignal = cir + base - ran;

    vec3 col;
    if (uLightMode > 0.5) {
        float peak = max(base.r, max(base.g, base.b));
        vec3 pigment = base / max(peak, 0.0001);
        float neutral = min(pigment.r, min(pigment.g, pigment.b));
        pigment = max(pigment - vec3(neutral * 0.72), vec3(0.0));
        pigment /= max(max(pigment.r, max(pigment.g, pigment.b)), 0.0001);
        pigment = mix(pigment, pigment * pigment, 0.12) * 0.72;
        vec3 revealed = clamp(revealSignal, 0.0, 1.0);
        float coverage = max(revealed.r, max(revealed.g, revealed.b));
        col = mix(vec3(1.0), pigment, coverage);
        float grain = max(rand(gl_FragCoord.xy + iTime) - 0.5, 0.0);
        float grainAmount = grain * uNoise * mix(0.12, 0.18, coverage);
        col = clamp(col - vec3(grainAmount), 0.0, 1.0);
    } else {
        col = revealSignal;
        col += (rand(gl_FragCoord.xy + iTime) - 0.5) * uNoise;
    }

    fragColor = vec4(col, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, vUv * iResolution.xy);
    gl_FragColor = color;
}
`;

export default function GradientBlinds({
  className = '',
  dpr = 1,
  gradientColors,
  angle = 0,
  noise = 0.3,
  blindCount = 16,
  blindMinWidth = 60,
  mouseDampening = 0.15,
  mirrorGradient = false,
  spotlightRadius = 0.5,
  spotlightSoftness = 1,
  spotlightOpacity = 1,
  distortAmount = 0,
  shineDirection = 'left',
  lightMode = false
}) {
  const conteneur = useRef(null);
  const reglages = useRef(null);
  reglages.current = { gradientColors, angle, noise, blindCount, blindMinWidth, mouseDampening, mirrorGradient, spotlightRadius, spotlightSoftness, spotlightOpacity, distortAmount, shineDirection, lightMode };

  useEffect(() => {
    const souris = [0, 0];
    let premier = true;
    let largeur = 1;
    const t = lancerToile(conteneur.current, {
      vertex,
      fragment,
      dpr,
      alpha: false,
      webgl: 1,
      pointeur: true,
      uniforms: {
        iResolution: { value: [1, 1, 1] },
        iMouse: { value: souris },
        iTime: { value: 0 },
        uAngle: { value: 0 },
        uNoise: { value: 0.3 },
        uBlindCount: { value: 16 },
        uSpotlightRadius: { value: 0.5 },
        uSpotlightSoftness: { value: 1 },
        uSpotlightOpacity: { value: 1 },
        uMirror: { value: 0 },
        uDistort: { value: 0 },
        uShineFlip: { value: 0 },
        ...Object.fromEntries(Array.from({ length: MAX_COLORS }, (_, i) => [`uColor${i}`, { value: [1, 1, 1] }])),
        uColorCount: { value: 2 },
        uLightMode: { value: 0 }
      },
      surTaille: (e, p) => {
        p.uniforms.iResolution.value = [e.w, e.h, 1];
        largeur = e.largeur;
        if (premier) {
          premier = false;
          souris[0] = e.w / 2;
          souris[1] = e.h / 2;
        }
      },
      avantRendu: ({ temps, dt, souris: s, program, etat }) => {
        const r = reglages.current;
        const u = program.uniforms;
        const cible = s.depuis > 0 ? [s.x * etat.w, (1 - s.y) * etat.h] : [etat.w / 2, etat.h / 2];
        const k = r.mouseDampening > 0 ? Math.min(1, 1 - Math.exp(-dt / Math.max(1e-4, r.mouseDampening))) : 1;
        souris[0] += (cible[0] - souris[0]) * k;
        souris[1] += (cible[1] - souris[1]) * k;
        const { arr, count } = prepStops(r.gradientColors);
        arr.forEach((c, i) => (u[`uColor${i}`].value = c));
        u.uColorCount.value = count;
        u.iTime.value = temps;
        u.uAngle.value = (r.angle * Math.PI) / 180;
        u.uNoise.value = r.noise;
        const parLargeur = r.blindMinWidth > 0 ? Math.max(1, Math.floor(largeur / r.blindMinWidth)) : Infinity;
        u.uBlindCount.value = Math.max(1, Math.min(r.blindCount || parLargeur, parLargeur));
        u.uSpotlightRadius.value = r.spotlightRadius;
        u.uSpotlightSoftness.value = r.spotlightSoftness;
        u.uSpotlightOpacity.value = r.spotlightOpacity;
        u.uMirror.value = r.mirrorGradient ? 1 : 0;
        u.uDistort.value = r.distortAmount;
        u.uShineFlip.value = r.shineDirection === 'right' ? 1 : 0;
        u.uLightMode.value = r.lightMode ? 1 : 0;
      }
    });
    return () => t.arreter();
  }, [dpr]);

  return <div ref={conteneur} className={`gradient-blinds-container ${className}`} />;
}
