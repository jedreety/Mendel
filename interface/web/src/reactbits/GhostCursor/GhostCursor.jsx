// GhostCursor de React Bits (reactbits.dev/animations/ghost-cursor). L'original tourne sur three.js, avec des passes
// de post-traitement (halo tres faible, grain, retour en alpha droit). Ici le meme shader de fumee tourne sur ogl
// par le socle commun (toile.js), pour ne pas ajouter de dependance : le grain et le retour en alpha droit sont
// faits dans le shader, le halo est retire. Sur un fond blanc, la fumee est composee normalement (l'original,
// fait pour un fond sombre, l'eclaircissait en mode ecran). Le rendu s'arrete quand la fumee s'est dissipee.
import { useEffect, useRef } from 'react';
import { lancerToile, rgb } from '../toile.js';
import './GhostCursor.css';

const vertex = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragment = n => `
precision highp float;
#define MAX_TRAIL_LENGTH ${n}
uniform float iTime;
uniform vec3  iResolution;
uniform vec2  iMouse;
uniform vec2  iPrevMouse[MAX_TRAIL_LENGTH];
uniform float iOpacity;
uniform float iScale;
uniform vec3  iBaseColor;
uniform float iBrightness;
uniform float iEdgeIntensity;
uniform float uGrain;
varying vec2  vUv;

float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7))) * 43758.5453123); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  f *= f * (3. - 2. * f);
  return mix(mix(hash(i + vec2(0.,0.)), hash(i + vec2(1.,0.)), f.x),
             mix(hash(i + vec2(0.,1.)), hash(i + vec2(1.,1.)), f.x), f.y);
}
float fbm(vec2 p){
  float v = 0.0;
  float a = 0.5;
  mat2 m = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
  for(int i=0;i<5;i++){
    v += a * noise(p);
    p = m * p * 2.0;
    a *= 0.5;
  }
  return v;
}
vec3 tint1(vec3 base){ return mix(base, vec3(1.0), 0.15); }
vec3 tint2(vec3 base){ return mix(base, vec3(0.8, 0.9, 1.0), 0.25); }

vec4 blob(vec2 p, vec2 mousePos, float intensity, float activity) {
  vec2 q = vec2(fbm(p * iScale + iTime * 0.1), fbm(p * iScale + vec2(5.2,1.3) + iTime * 0.1));
  vec2 r = vec2(fbm(p * iScale + q * 1.5 + iTime * 0.15), fbm(p * iScale + q * 1.5 + vec2(8.3,2.8) + iTime * 0.15));

  float smoke = fbm(p * iScale + r * 0.8);
  float radius = 0.5 + 0.3 * (1.0 / iScale);
  float distFactor = 1.0 - smoothstep(0.0, radius * activity, length(p - mousePos));
  float alpha = pow(smoke, 2.5) * distFactor;

  vec3 c1 = tint1(iBaseColor);
  vec3 c2 = tint2(iBaseColor);
  vec3 color = mix(c1, c2, sin(iTime * 0.5) * 0.5 + 0.5);

  return vec4(color * alpha * intensity, alpha * intensity);
}

void main() {
  vec2 uv = (gl_FragCoord.xy / iResolution.xy * 2.0 - 1.0) * vec2(iResolution.x / iResolution.y, 1.0);
  vec2 mouse = (iMouse * 2.0 - 1.0) * vec2(iResolution.x / iResolution.y, 1.0);

  vec3 colorAcc = vec3(0.0);
  float alphaAcc = 0.0;

  vec4 b = blob(uv, mouse, 1.0, iOpacity);
  colorAcc += b.rgb;
  alphaAcc += b.a;

  for (int i = 0; i < MAX_TRAIL_LENGTH; i++) {
    vec2 pm = (iPrevMouse[i] * 2.0 - 1.0) * vec2(iResolution.x / iResolution.y, 1.0);
    float t = 1.0 - float(i) / float(MAX_TRAIL_LENGTH);
    t = pow(t, 2.0);
    if (t > 0.01) {
      vec4 bt = blob(uv, pm, t * 0.8, iOpacity);
      colorAcc += bt.rgb;
      alphaAcc += bt.a;
    }
  }

  colorAcc *= iBrightness;

  vec2 uv01 = gl_FragCoord.xy / iResolution.xy;
  float edgeDist = min(min(uv01.x, 1.0 - uv01.x), min(uv01.y, 1.0 - uv01.y));
  float distFromEdge = clamp(edgeDist * 2.0, 0.0, 1.0);
  float k = clamp(iEdgeIntensity, 0.0, 1.0);
  float edgeMask = mix(1.0 - k, 1.0, distFromEdge);

  float outAlpha = clamp(alphaAcc * iOpacity * edgeMask, 0.0, 1.0);
  vec3 c = clamp(colorAcc, 0.0, 1.0) * outAlpha;
  float n = fract(sin(vUv.x * 1000.0 + vUv.y * 2000.0 + iTime) * 43758.5453) * 2.0 - 1.0;
  c = clamp(c + n * uGrain * c, 0.0, 1.0);
  float coverage = max(c.r, max(c.g, c.b));
  gl_FragColor = vec4(c, coverage);
}
`;

export default function GhostCursor({
  className = '',
  style,
  trailLength = 24,
  inertia = 0.5,
  grainIntensity = 0.05,
  brightness = 1,
  color = '#B497CF',
  edgeIntensity = 0,
  dpr = 0.5,
  fadeDelayMs = 1000,
  fadeDurationMs = 1500
}) {
  const conteneur = useRef(null);
  const reglages = useRef(null);
  reglages.current = { inertia, grainIntensity, brightness, color, edgeIntensity, fadeDelayMs, fadeDurationMs };

  useEffect(() => {
    const n = Math.max(1, Math.floor(trailLength));
    const trace = Array.from({ length: n }, () => [0.5, 0.5]);
    const souris = [0.5, 0.5];
    const vitesse = [0, 0];
    let tete = 0;
    let opacite = 0;
    let dernierMouvement = -Infinity;
    const t = lancerToile(conteneur.current, {
      vertex,
      fragment: fragment(n),
      dpr,
      alpha: true,
      premultipliedAlpha: true,
      webgl: 1,
      pointeur: true,
      uniforms: {
        iTime: { value: 0 },
        iResolution: { value: [1, 1, 1] },
        iMouse: { value: souris },
        iPrevMouse: { value: trace.map(p => [...p]) },
        iOpacity: { value: 0 },
        iScale: { value: 1 },
        iBaseColor: { value: [1, 1, 1] },
        iBrightness: { value: 1 },
        iEdgeIntensity: { value: 0 },
        uGrain: { value: 0.05 }
      },
      surTaille: (e, p) => {
        p.uniforms.iResolution.value = [e.w, e.h, 1];
        p.uniforms.iScale.value = Math.max(0.5, Math.min(2, Math.min(e.largeur, e.hauteur) / 600));
      },
      avantRendu: ({ temps, souris: s, program, maintenant }) => {
        const r = reglages.current;
        const u = program.uniforms;
        const actif = s.dans && maintenant - s.depuis < 120;
        if (actif) {
          const x = Math.min(1, Math.max(0, s.x));
          const y = Math.min(1, Math.max(0, 1 - s.y));
          vitesse[0] = x - souris[0];
          vitesse[1] = y - souris[1];
          souris[0] = x;
          souris[1] = y;
          dernierMouvement = maintenant;
          opacite = 1;
        } else {
          vitesse[0] *= r.inertia;
          vitesse[1] *= r.inertia;
          souris[0] += vitesse[0];
          souris[1] += vitesse[1];
          const attente = maintenant - dernierMouvement;
          if (attente > r.fadeDelayMs) opacite = Math.max(0, 1 - (attente - r.fadeDelayMs) / r.fadeDurationMs);
        }
        if (opacite <= 0.001 && u.iOpacity.value <= 0.001) return false;
        tete = (tete + 1) % n;
        trace[tete][0] = souris[0];
        trace[tete][1] = souris[1];
        const liste = u.iPrevMouse.value;
        for (let i = 0; i < n; i++) {
          const src = trace[(tete - i + n) % n];
          liste[i][0] = src[0];
          liste[i][1] = src[1];
        }
        u.iOpacity.value = opacite;
        u.iTime.value = temps;
        u.iBaseColor.value = rgb(r.color);
        u.iBrightness.value = r.brightness;
        u.iEdgeIntensity.value = r.edgeIntensity;
        u.uGrain.value = r.grainIntensity;
      }
    });
    return () => t.arreter();
  }, [trailLength, dpr]);

  return <div ref={conteneur} className={`ghost-cursor ${className}`} style={style} />;
}
