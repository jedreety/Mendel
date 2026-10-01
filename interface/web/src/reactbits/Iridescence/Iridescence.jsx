// Iridescence de React Bits (reactbits.dev/backgrounds/iridescence), shader repris tel quel. Adapte : pose sur le
// socle commun (toile.js) ; le pointeur est suivi sur toute la fenetre, le portrait qu'il habille etant recouvert.
import { useEffect, useRef } from 'react';
import { lancerToile } from '../toile.js';
import './Iridescence.css';

const vertexShader = `
attribute vec2 uv;
attribute vec2 position;

varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

const fragmentShader = `
precision highp float;

uniform float uTime;
uniform vec3 uColor;
uniform vec3 uResolution;
uniform vec2 uMouse;
uniform float uAmplitude;
uniform float uSpeed;

varying vec2 vUv;

void main() {
  float mr = min(uResolution.x, uResolution.y);
  vec2 uv = (vUv.xy * 2.0 - 1.0) * uResolution.xy / mr;

  uv += (uMouse - vec2(0.5)) * uAmplitude;

  float d = -uTime * 0.5 * uSpeed;
  float a = 0.0;
  for (float i = 0.0; i < 8.0; ++i) {
    a += cos(i - d - a * uv.x);
    d += sin(uv.y * i + a);
  }
  d += uTime * 0.5 * uSpeed;
  vec3 col = vec3(cos(uv * vec2(d, a)) * 0.6 + 0.4, cos(a + d) * 0.5 + 0.5);
  col = cos(col * cos(vec3(d, a, 2.5)) * 0.5 + 0.5) * uColor;
  gl_FragColor = vec4(col, 1.0);
}
`;

export default function Iridescence({ color = [1, 1, 1], speed = 1.0, amplitude = 0.1, mouseReact = true, dpr = 1, className = '' }) {
  const conteneur = useRef(null);
  const reglages = useRef(null);
  reglages.current = { color, speed, amplitude, mouseReact };

  useEffect(() => {
    const souris = [0.5, 0.5];
    const t = lancerToile(conteneur.current, {
      vertex: vertexShader,
      fragment: fragmentShader,
      dpr,
      alpha: false,
      webgl: 1,
      pointeur: true,
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: [1, 1, 1] },
        uResolution: { value: [1, 1, 1] },
        uMouse: { value: souris },
        uAmplitude: { value: 0.1 },
        uSpeed: { value: 1 }
      },
      surTaille: (e, p) => (p.uniforms.uResolution.value = [e.w, e.h, e.w / e.h]),
      avantRendu: ({ temps, dt, souris: s, program }) => {
        const r = reglages.current;
        const u = program.uniforms;
        if (r.mouseReact) {
          const k = 1 - Math.exp(-dt / 0.25);
          souris[0] += (Math.min(1, Math.max(0, s.x)) - souris[0]) * k;
          souris[1] += (1 - Math.min(1, Math.max(0, s.y)) - souris[1]) * k;
        }
        u.uTime.value = temps;
        u.uColor.value = r.color;
        u.uSpeed.value = r.speed;
        u.uAmplitude.value = r.amplitude;
      }
    });
    return () => t.arreter();
  }, [dpr]);

  return <div ref={conteneur} className={`iridescence-container ${className}`} />;
}
