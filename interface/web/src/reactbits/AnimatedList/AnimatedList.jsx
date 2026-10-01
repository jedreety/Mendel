// AnimatedList de React Bits (reactbits.dev/components/animated-list), adapte : chaque element est rendu par
// renderItem ; les fleches et Entree ne sont ecoutees que quand la liste a le focus (l'original les prenait a toute
// la page, Tab compris) ; l'entree des elements est plus douce et ne se joue qu'une fois ; fondus blancs.
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'motion/react';
import './AnimatedList.css';

const SORTIE = [0.23, 1, 0.32, 1];

function AnimatedItem({ children, delay, index, onMouseEnter, onClick }) {
  const ref = useRef(null);
  const inView = useInView(ref, { amount: 0.3, once: true });
  return (
    <motion.div
      ref={ref}
      data-index={index}
      className="animated-list__element"
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      initial={{ opacity: 0, y: 8, scale: 0.985 }}
      animate={inView ? { opacity: 1, y: 0, scale: 1 } : undefined}
      transition={{ duration: 0.4, delay, ease: SORTIE }}
    >
      {children}
    </motion.div>
  );
}

export default function AnimatedList({
  items = [],
  renderItem,
  getKey,
  onItemSelect,
  showGradients = true,
  enableArrowNavigation = true,
  className = '',
  itemClassName = '',
  displayScrollbar = false,
  maxHeight,
  stagger = 0.045,
  label = 'Liste'
}) {
  const listRef = useRef(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [keyboardNav, setKeyboardNav] = useState(false);
  const [haut, setHaut] = useState(0);
  const [bas, setBas] = useState(0);

  const mesurer = useCallback(el => {
    const { scrollTop, scrollHeight, clientHeight } = el;
    setHaut(Math.min(scrollTop / 50, 1));
    setBas(scrollHeight <= clientHeight ? 0 : Math.min((scrollHeight - scrollTop - clientHeight) / 50, 1));
  }, []);

  useEffect(() => {
    if (listRef.current) mesurer(listRef.current);
  }, [items, mesurer]);

  useEffect(() => {
    if (!keyboardNav || selectedIndex < 0 || !listRef.current) return;
    listRef.current.querySelector(`[data-index="${selectedIndex}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    setKeyboardNav(false);
  }, [selectedIndex, keyboardNav]);

  const onKeyDown = e => {
    if (!enableArrowNavigation || !items.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setKeyboardNav(true);
      setSelectedIndex(p => Math.min(p + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setKeyboardNav(true);
      setSelectedIndex(p => Math.max(p - 1, 0));
    } else if (e.key === 'Enter' && selectedIndex >= 0 && selectedIndex < items.length) {
      e.preventDefault();
      onItemSelect?.(items[selectedIndex], selectedIndex);
    }
  };

  return (
    <div className={`scroll-list-container ${className}`}>
      <div
        ref={listRef}
        role="list"
        aria-label={label}
        tabIndex={enableArrowNavigation && onItemSelect ? 0 : undefined}
        className={`scroll-list ${displayScrollbar ? '' : 'no-scrollbar'}`}
        style={maxHeight ? { maxHeight } : undefined}
        onKeyDown={onKeyDown}
        onScroll={e => mesurer(e.currentTarget)}
        onMouseLeave={() => setSelectedIndex(-1)}
      >
        {items.map((item, index) => (
          <AnimatedItem
            key={getKey ? getKey(item, index) : index}
            delay={Math.min(index, 8) * stagger}
            index={index}
            onMouseEnter={() => setSelectedIndex(index)}
            onClick={() => {
              setSelectedIndex(index);
              onItemSelect?.(item, index);
            }}
          >
            <div role="listitem" className={`item ${onItemSelect ? 'cliquable' : ''} ${selectedIndex === index ? 'selected' : ''} ${itemClassName}`}>
              {renderItem ? renderItem(item, index, selectedIndex === index) : <p className="item-text">{item}</p>}
            </div>
          </AnimatedItem>
        ))}
      </div>
      {showGradients && (
        <>
          <div className="top-gradient" style={{ opacity: haut }} />
          <div className="bottom-gradient" style={{ opacity: bas }} />
        </>
      )}
    </div>
  );
}
