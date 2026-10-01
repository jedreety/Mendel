// PromptBar de React Bits (reactbits.dev/micro/prompt-bar), adapte en barre de commande : « / » ouvre les actions,
// « @ » les bots, un texte libre cherche parmi ce que rechercher() rend ; choisir une ligne appelle onPick. Retires :
// pieces jointes, choix du modele et de l'effort, dictee, sans objet ici. Gardes : le menu et son surlignage qui
// glisse, la tuile d'envoi qui se charge quand il y a de quoi partir. Une seule ligne, menu dessous ou dessus,
// icones maison, couleurs claires, textes en francais.
import { isValidElement, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { animate, useMotionValue, useMotionValueEvent, useReducedMotion } from 'motion/react';
import Icone from '../../composants/Icone.jsx';
import { ENCRE } from '../../palette.js';
import './PromptBar.css';

const ARROW_UP = [12, 4.5, 18.5, 11, 14.25, 11, 14.25, 19.5, 9.75, 19.5, 9.75, 11, 5.5, 11];
const SQUARE = [12, 6, 18, 6, 18, 12, 18, 18, 6, 18, 6, 12, 6, 6];
const EASE_IN_OUT = [0.77, 0, 0.175, 1];

const mix = (a, b, t) => a + (b - a) * t;
const pathAt = (a, b, t) => {
  let d = '';
  for (let i = 0; i < a.length; i += 2) {
    d += `${i ? 'L' : 'M'}${mix(a[i], b[i], t).toFixed(2)} ${mix(a[i + 1], b[i + 1], t).toFixed(2)}`;
  }
  return `${d}Z`;
};
const norm = s =>
  String(s ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();

const parseToken = draft => {
  const m = /(^|\s)([@/])([\p{L}\p{N}_-]*)$/u.exec(draft);
  if (!m) return null;
  return { kind: m[2] === '@' ? 'at' : 'slash', query: norm(m[3]), start: m.index + m[1].length };
};

const renderIcon = icon => (isValidElement(icon) ? icon : typeof icon === 'string' ? <Icone nom={icon} taille={15} /> : null);

function SendGlyph({ busy, morphDuration, squash, tilt }) {
  const reduce = useReducedMotion();
  const svgRef = useRef(null);
  const pathRef = useRef(null);
  const dir = useRef(busy ? 1 : -1);
  const t = useMotionValue(busy ? 1 : 0);

  useEffect(() => {
    const target = busy ? 1 : 0;
    dir.current = busy ? 1 : -1;
    if (t.get() === target) return undefined;
    const controls = animate(t, target, reduce ? { duration: 0 } : { duration: morphDuration / 1000, ease: EASE_IN_OUT });
    return () => controls.stop();
  }, [busy, morphDuration, reduce, t]);

  useMotionValueEvent(t, 'change', v => {
    pathRef.current?.setAttribute('d', pathAt(ARROW_UP, SQUARE, v));
    const goo = reduce ? 0 : Math.sin(v * Math.PI);
    const sx = 1 - squash * goo;
    if (svgRef.current) {
      svgRef.current.style.transform = goo ? `rotate(${dir.current * tilt * goo}deg) scale(${sx}, ${1 / sx})` : '';
    }
  });

  return (
    <svg ref={svgRef} className="prompt-bar__glyph" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
      <path ref={pathRef} d={pathAt(ARROW_UP, SQUARE, t.get())} />
    </svg>
  );
}

export default function PromptBar({
  placeholder = 'Aller à…',
  sources = [],
  commands = [],
  rechercher,
  onPick,
  onEscape,
  busy = false,
  background = '#ffffff',
  color = ENCRE,
  menuBackground = '#ffffff',
  width = 560,
  radius = 16,
  menuPlacement = 'bottom',
  maxMenuRows = 7,
  autoFocus = false,
  morphDuration = 240,
  squash = 0.12,
  tilt = 8,
  pressScale = 0.96,
  className = ''
}) {
  const rootRef = useRef(null);
  const inputRef = useRef(null);
  const menuRef = useRef(null);
  const glowRef = useRef(null);
  const rowRefs = useRef([]);
  const lastOpen = useRef(null);
  const latest = useRef({});
  latest.current = { onPick, onEscape };

  const [draft, setDraft] = useState('');
  const [plusOpen, setPlusOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [active, setActive] = useState(0);
  const [pressed, setPressed] = useState(false);

  const token = dismissed ? null : parseToken(draft);
  const libre = !token && !dismissed && draft.trim() && rechercher ? 'libre' : null;
  const open = plusOpen ? 'at' : (token?.kind ?? libre);
  const query = plusOpen ? '' : (token?.query ?? norm(draft.trim()));
  const list = useMemo(() => {
    if (open === 'at') return sources.filter(s => norm(s.name).includes(query) || norm(s.description).includes(query));
    if (open === 'slash') return commands.filter(c => norm(c.name.replace(/^\//, '')).startsWith(query) || norm(c.description).includes(query));
    if (open === 'libre') return rechercher(draft.trim());
    return [];
  }, [open, query, sources, commands, rechercher, draft]);
  const cursor = Math.min(active, Math.max(0, list.length - 1));
  const canSend = open ? list.length > 0 : draft.trim().length > 0;
  const armed = busy || canSend;

  const focusInput = () => inputRef.current?.focus({ preventScroll: true });

  useEffect(() => {
    if (autoFocus) focusInput();
  }, [autoFocus]);

  useLayoutEffect(() => {
    const glow = glowRef.current;
    if (!glow || !open) return;
    const row = rowRefs.current[cursor];
    if (!row) {
      glow.style.opacity = '0';
      return;
    }
    const fresh = lastOpen.current !== open;
    lastOpen.current = open;
    if (fresh) glow.style.transition = 'none';
    glow.style.top = `${row.offsetTop}px`;
    glow.style.height = `${row.offsetHeight}px`;
    glow.style.opacity = '1';
    row.scrollIntoView({ block: 'nearest' });
    if (fresh) {
      void glow.offsetHeight;
      glow.style.transition = '';
    }
  }, [open, cursor, list]);
  useEffect(() => {
    if (!open) lastOpen.current = null;
  }, [open]);

  useEffect(() => {
    if (!plusOpen) return undefined;
    const onDown = e => {
      if (!rootRef.current?.contains(e.target)) setPlusOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [plusOpen]);

  const pick = row => {
    if (!row) return;
    setDraft('');
    setPlusOpen(false);
    setDismissed(false);
    setActive(0);
    latest.current.onPick?.(row, open);
  };

  const onKeyDown = e => {
    if (open && list.length) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        setActive((cursor + (e.key === 'ArrowDown' ? 1 : list.length - 1)) % list.length);
        return;
      }
      if ((e.key === 'Enter' && !e.shiftKey) || e.key === 'Tab') {
        e.preventDefault();
        pick(list[cursor]);
        return;
      }
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      if (open) {
        setDismissed(true);
        setPlusOpen(false);
      } else latest.current.onEscape?.();
      return;
    }
    if (e.key === 'Enter') e.preventDefault();
  };

  const down = e => {
    if (e.button !== 0 || !armed) return;
    setPressed(true);
  };
  const up = () => setPressed(false);

  return (
    <div
      ref={rootRef}
      className={`prompt-bar${className ? ` ${className}` : ''}`}
      data-busy={busy ? '' : undefined}
      data-placement={menuPlacement}
      style={{
        '--pb-bg': background,
        '--pb-ink': color,
        '--pb-menu': menuBackground,
        '--pb-w': `${width}px`,
        '--pb-radius': `${radius}px`,
        '--pb-press': pressScale,
        '--pb-rows': maxMenuRows
      }}
    >
      {open ? (
        <div ref={menuRef} className="prompt-bar__menu" role="listbox" aria-label={open === 'at' ? 'Bots' : open === 'slash' ? 'Actions' : 'Résultats'} data-kind={open}>
          <span ref={glowRef} className="prompt-bar__glow" aria-hidden="true" />
          {list.map((row, i) => (
            <button
              key={row.key}
              ref={el => {
                rowRefs.current[i] = el;
              }}
              type="button"
              role="option"
              aria-selected={i === cursor}
              className="prompt-bar__row"
              onMouseDown={e => e.preventDefault()}
              onPointerEnter={() => setActive(i)}
              onClick={() => pick(row)}
            >
              <span className="prompt-bar__row-icon">{renderIcon(row.icon)}</span>
              <span className="prompt-bar__row-name">{row.name}</span>
              {row.description ? <span className="prompt-bar__row-desc">{row.description}</span> : null}
              {row.tag ? <span className="prompt-bar__row-tag">{row.tag}</span> : null}
            </button>
          ))}
          {list.length === 0 ? <div className="prompt-bar__empty">Rien ne correspond à « {draft.replace(/^.*[@/]/, '').trim() || draft} »</div> : null}
        </div>
      ) : null}

      <div className="prompt-bar__field" role="presentation" onClick={focusInput}>
        <button
          type="button"
          className="prompt-bar__tool"
          aria-label="Choisir un bot"
          aria-expanded={plusOpen}
          data-on={plusOpen ? '' : undefined}
          onMouseDown={e => e.preventDefault()}
          onClick={e => {
            e.stopPropagation();
            setActive(0);
            setDismissed(false);
            setPlusOpen(v => !v);
            focusInput();
          }}
        >
          <Icone nom="recherche" taille={16} epaisseur={2} />
        </button>
        <input
          ref={inputRef}
          className="prompt-bar__input"
          value={draft}
          placeholder={placeholder}
          aria-label="Commande"
          autoComplete="off"
          spellCheck={false}
          onChange={e => {
            setDraft(e.target.value);
            setDismissed(false);
            setPlusOpen(false);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
        />
        <button
          type="button"
          className="prompt-bar__send"
          disabled={!armed}
          aria-label="Aller"
          data-armed={armed ? '' : undefined}
          data-pressed={pressed ? '' : undefined}
          onMouseDown={e => e.preventDefault()}
          onPointerDown={down}
          onPointerUp={up}
          onPointerCancel={up}
          onPointerLeave={up}
          onClick={e => {
            e.stopPropagation();
            if (open && list.length) pick(list[cursor]);
          }}
        >
          <SendGlyph busy={busy} morphDuration={morphDuration} squash={squash} tilt={tilt} />
        </button>
      </div>
    </div>
  );
}
