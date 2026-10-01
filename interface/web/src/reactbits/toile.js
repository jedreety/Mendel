// Socle des fonds WebGL de React Bits portes ou repris ici : un triangle plein ecran, un programme, la taille
// suivie, le rendu suspendu hors de l'ecran et dans un onglet cache, la resolution plafonnee (un fond flou n'a
// pas besoin de la pleine definition, et la GPU sert d'abord au bot), le pointeur suivi sur toute la fenetre :
// le contenu de la page passe au-dessus du fond et prendrait ses evenements.
import { Mesh, Program, Renderer, Triangle } from 'ogl';

export function lancerToile(conteneur, options) {
  const { vertex, fragment, dpr = 1, alpha = true, premultipliedAlpha = false, webgl = 2, pointeur = false, surTaille, avantRendu } = options;
  const renderer = new Renderer({ dpr: Math.min(dpr, window.devicePixelRatio || 1), alpha, premultipliedAlpha, antialias: false, webgl, powerPreference: 'low-power' });
  const gl = renderer.gl;
  // Transparent : noir d'alpha nul. Un blanc d'alpha nul n'est pas une couleur premultipliee valide, et le
  // navigateur l'ajouterait au fond de la page.
  if (alpha) gl.clearColor(0, 0, 0, 0);
  else gl.clearColor(1, 1, 1, 1);
  const toile = gl.canvas;
  toile.style.display = 'block';
  toile.style.width = '100%';
  toile.style.height = '100%';
  conteneur.appendChild(toile);

  const uniforms = typeof options.uniforms === 'function' ? options.uniforms(gl) : options.uniforms;
  const program = new Program(gl, { vertex, fragment, uniforms, transparent: alpha, depthTest: false, depthWrite: false });
  const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });

  const etat = { largeur: 1, hauteur: 1, w: 1, h: 1, dpr: renderer.dpr };
  const taille = () => {
    etat.largeur = conteneur.clientWidth || 1;
    etat.hauteur = conteneur.clientHeight || 1;
    renderer.setSize(etat.largeur, etat.hauteur);
    etat.w = gl.drawingBufferWidth;
    etat.h = gl.drawingBufferHeight;
    surTaille?.(etat, program);
  };
  const observateur = new ResizeObserver(taille);
  observateur.observe(conteneur);
  taille();

  let visible = true;
  const vue = new IntersectionObserver(([e]) => (visible = e.isIntersecting), { threshold: 0 });
  vue.observe(conteneur);

  // x, y de 0 a 1 dans le conteneur, y vers le bas ; dans : le pointeur est au-dessus ; depuis : dernier mouvement.
  const souris = { x: 0.5, y: 0.5, dans: false, depuis: -Infinity };
  const suivre = e => {
    const r = conteneur.getBoundingClientRect();
    souris.x = (e.clientX - r.left) / Math.max(1, r.width);
    souris.y = (e.clientY - r.top) / Math.max(1, r.height);
    souris.dans = souris.x >= 0 && souris.x <= 1 && souris.y >= 0 && souris.y <= 1;
    souris.depuis = performance.now();
  };
  if (pointeur) window.addEventListener('pointermove', suivre, { passive: true });

  let raf = 0;
  let avant = performance.now();
  let temps = 0;
  const boucle = maintenant => {
    raf = requestAnimationFrame(boucle);
    const dt = Math.min(0.1, Math.max(0, (maintenant - avant) / 1000));
    avant = maintenant;
    if (!visible || document.hidden) return;
    temps += dt;
    if (avantRendu?.({ temps, dt, souris, maintenant, program, etat }) === false) return;
    renderer.render({ scene: mesh });
  };
  raf = requestAnimationFrame(boucle);

  return {
    gl,
    program,
    arreter() {
      cancelAnimationFrame(raf);
      observateur.disconnect();
      vue.disconnect();
      if (pointeur) window.removeEventListener('pointermove', suivre);
      toile.remove();
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  };
}

export function rgb(hex) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? [...h].map(c => c + c).join('') : h.slice(0, 6), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}
