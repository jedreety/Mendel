// CallChip de React Bits (reactbits.dev/micro/call-chip), adapte : icones maison, textes en francais, et
// chronometre compte depuis l'instant de lancement de la tache (depuis, en millisecondes locales), pas depuis
// l'affichage : une tache lancee il y a une heure affiche une heure. dureeMs fige la duree d'une tache finie.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Icone from '../../composants/Icone.jsx';
import './CallChip.css';

const HOLD_AT = 0.9;
const SHAKE = [0, -1, 1, -0.66, 0.66, -0.33, 0];
const WORDS = { running: 'en cours', done: 'terminé', error: 'échec', idle: 'en attente' };

const fmt = ms => {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, '0')}`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
};
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
const glyphOf = s => (s === 'done' ? 'check' : s === 'error' ? 'retry' : 'tool');

export default function CallChip({
  icon = 'eclair',
  name = '',
  argument = '',
  status = 'running',
  depuis,
  dureeMs,
  expectedMs = 2500,
  size = 34,
  radius = 10,
  color = 'currentColor',
  surfaceColor = '#f5f5f7',
  progressColor = 'currentColor',
  progressOpacity = 0.08,
  doneColor = '#16a34a',
  errorColor = '#e5484d',
  washOpacity = 0.14,
  shake = 6,
  showTimer = true,
  onRetry,
  className = '',
  style
}) {
  const rootRef = useRef(null);
  const fillRef = useRef(null);
  const timerRef = useRef(null);
  const mountedRef = useRef(false);
  const fraction = useRef(0);
  const clock = useRef({ ms: 0 });
  const shakeAnim = useRef(null);
  const statusRef = useRef(status);
  statusRef.current = status;
  const [mounted, setMounted] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [announce, setAnnounce] = useState('');
  const roll = useRef({ cur: glyphOf(status), prev: null });
  if (glyphOf(status) !== roll.current.cur) roll.current = { cur: glyphOf(status), prev: roll.current.cur };

  const setFraction = (f, instant) => {
    const fill = fillRef.current;
    if (!fill) return;
    fraction.current = f;
    if (instant) fill.style.transition = 'none';
    fill.style.transform = `scaleX(${f})`;
    if (instant) {
      void fill.getBoundingClientRect();
      fill.style.transition = '';
    }
  };
  const apply = (s, animate) => {
    if (s === 'running') {
      shakeAnim.current?.cancel();
      setFraction(0, true);
      if (animate) setFraction(HOLD_AT, false);
    } else if (s === 'done') {
      setFraction(1, !animate);
    } else if (s === 'error') {
      const fill = fillRef.current;
      const live = fill ? new DOMMatrix(getComputedStyle(fill).transform).a : fraction.current;
      setFraction(Math.min(1, Math.max(0, live)), true);
      if (animate && shake > 0 && !reduceMotion() && rootRef.current) {
        shakeAnim.current = rootRef.current.animate(
          SHAKE.map(k => ({ transform: `translateX(${k * shake}px)`, easing: 'cubic-bezier(0.77, 0, 0.175, 1)' })),
          { duration: 450, composite: 'add' }
        );
      }
    } else setFraction(0, true);
  };

  useEffect(() => {
    mountedRef.current = true;
    setMounted(true);
    apply(statusRef.current, statusRef.current === 'running');
    return () => {
      mountedRef.current = false;
      shakeAnim.current?.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useLayoutEffect(() => {
    if (mountedRef.current) apply(status, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Une seconde de resolution suffit a un chronometre de tache : pas d'animation image par image.
  useEffect(() => {
    const debut = depuis ?? Date.now();
    const write = () => {
      clock.current.ms = dureeMs ?? Date.now() - debut;
      if (timerRef.current) timerRef.current.textContent = fmt(clock.current.ms);
    };
    write();
    if (status !== 'running') return undefined;
    const id = setInterval(write, 1000);
    return () => clearInterval(id);
  }, [status, depuis, dureeMs]);
  useEffect(() => {
    setAnnounce(`${name} ${argument}, ${WORDS[status] ?? status}`);
  }, [status, name, argument]);

  const font = Math.max(11, Math.round(size * 0.38));
  const glyphState = g => (g === roll.current.cur ? 'in' : g === roll.current.prev ? 'out' : undefined);
  const iconSize = font + 2;

  return (
    <span
      ref={rootRef}
      role="status"
      aria-busy={status === 'running' || undefined}
      data-status={status}
      data-mounted={mounted ? '' : undefined}
      data-pressed={pressed ? '' : undefined}
      className={`call-chip${className ? ` ${className}` : ''}`}
      style={{
        '--cc-size': `${size}px`,
        '--cc-font': `${font}px`,
        '--cc-pad': `${Math.round(size * 0.35)}px`,
        '--cc-gap': `${Math.round(font * 0.55)}px`,
        '--cc-radius': `${radius}px`,
        '--cc-color': color,
        '--cc-surface': surfaceColor,
        '--cc-progress': progressColor,
        '--cc-progress-pct': `${progressOpacity * 100}%`,
        '--cc-done': doneColor,
        '--cc-error': errorColor,
        '--cc-wash-pct': `${washOpacity * 100}%`,
        '--cc-expected': `${expectedMs}ms`,
        ...style
      }}
    >
      <span ref={fillRef} className="call-chip__fill" aria-hidden="true" />
      <span className="call-chip__slot" aria-hidden="true">
        <span className="call-chip__glyph" data-state={glyphState('tool')}>
          <Icone nom={icon} taille={iconSize} />
        </span>
        <span className="call-chip__glyph" data-state={glyphState('check')}>
          <Icone nom="coche" taille={iconSize} epaisseur={2.2} />
        </span>
        <span className="call-chip__glyph" data-state={glyphState('retry')}>
          <Icone nom="rafraichir" taille={iconSize} epaisseur={2} />
        </span>
      </span>
      <span className="call-chip__name" aria-hidden="true">
        {name}
      </span>
      {argument ? (
        <span className="call-chip__arg" aria-hidden="true">
          {argument}
        </span>
      ) : null}
      {showTimer ? (
        <span ref={timerRef} className="call-chip__timer" aria-hidden="true">
          0 s
        </span>
      ) : null}
      {status === 'error' && onRetry ? (
        <button
          type="button"
          className="call-chip__retry"
          aria-label={`Relancer ${name} ${argument}`}
          onClick={() => onRetry()}
          onPointerDown={() => setPressed(true)}
          onPointerUp={() => setPressed(false)}
          onPointerCancel={() => setPressed(false)}
        />
      ) : null}
      <span className="call-chip__sr">{announce}</span>
    </span>
  );
}
