// ScrollVelocity de React Bits (reactbits.dev/text-animations/scroll-velocity), adapte : le texte defilant est
// sorti du composant (defini dedans, il etait recree, donc remonte, a chaque rendu), et chaque texte peut etre
// un element React. Le defilement accelere quand on fait defiler la page.
import { useLayoutEffect, useRef, useState } from 'react';
import { motion, useAnimationFrame, useMotionValue, useScroll, useSpring, useTransform, useVelocity } from 'motion/react';
import './ScrollVelocity.css';

function useElementWidth(ref) {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(() => setWidth(el.offsetWidth));
    observer.observe(el);
    setWidth(el.offsetWidth);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

const wrap = (min, max, v) => {
  const range = max - min;
  return ((((v - min) % range) + range) % range) + min;
};

function VelocityText({ children, baseVelocity, scrollContainerRef, className, damping, stiffness, numCopies, velocityMapping, parallaxClassName, scrollerClassName, parallaxStyle, scrollerStyle }) {
  const baseX = useMotionValue(0);
  const { scrollY } = useScroll(scrollContainerRef ? { container: scrollContainerRef } : {});
  const scrollVelocity = useVelocity(scrollY);
  const smoothVelocity = useSpring(scrollVelocity, { damping: damping ?? 50, stiffness: stiffness ?? 400 });
  const velocityFactor = useTransform(smoothVelocity, velocityMapping?.input || [0, 1000], velocityMapping?.output || [0, 5], { clamp: false });
  const copyRef = useRef(null);
  const copyWidth = useElementWidth(copyRef);
  const x = useTransform(baseX, v => (copyWidth === 0 ? '0px' : `${wrap(-copyWidth, 0, v)}px`));
  const directionFactor = useRef(1);

  useAnimationFrame((t, delta) => {
    let moveBy = directionFactor.current * baseVelocity * (delta / 1000);
    if (velocityFactor.get() < 0) directionFactor.current = -1;
    else if (velocityFactor.get() > 0) directionFactor.current = 1;
    moveBy += directionFactor.current * moveBy * velocityFactor.get();
    baseX.set(baseX.get() + moveBy);
  });

  return (
    <div className={parallaxClassName} style={parallaxStyle}>
      <motion.div className={scrollerClassName} style={{ x, ...scrollerStyle }}>
        {Array.from({ length: numCopies }, (_, i) => (
          <span className={className} key={i} ref={i === 0 ? copyRef : null} aria-hidden={i > 0 || undefined}>
            {children}&nbsp;
          </span>
        ))}
      </motion.div>
    </div>
  );
}

export default function ScrollVelocity({
  scrollContainerRef,
  texts = [],
  velocity = 100,
  className = '',
  damping = 50,
  stiffness = 400,
  numCopies = 6,
  velocityMapping = { input: [0, 1000], output: [0, 5] },
  parallaxClassName = 'parallax',
  scrollerClassName = 'scroller',
  parallaxStyle,
  scrollerStyle
}) {
  return (
    <section>
      {texts.map((text, index) => (
        <VelocityText
          key={index}
          className={className}
          baseVelocity={index % 2 !== 0 ? -velocity : velocity}
          scrollContainerRef={scrollContainerRef}
          damping={damping}
          stiffness={stiffness}
          numCopies={numCopies}
          velocityMapping={velocityMapping}
          parallaxClassName={parallaxClassName}
          scrollerClassName={scrollerClassName}
          parallaxStyle={parallaxStyle}
          scrollerStyle={scrollerStyle}
        >
          {text}
        </VelocityText>
      ))}
    </section>
  );
}
