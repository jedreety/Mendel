// TiltedCard de React Bits (reactbits.dev/components/tilted-card), adapte : la carte porte un contenu quelconque
// (children) au lieu d'une image, sans l'etiquette qui suit le pointeur ; inclinaison et agrandissement plus
// discrets, comme il sied a une carte de texte. Les ressorts sont ceux de l'original.
import { useRef } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react';
import './TiltedCard.css';

const springValues = { damping: 30, stiffness: 100, mass: 2 };

export default function TiltedCard({ children, rotateAmplitude = 7, scaleOnHover = 1.015, className = '', style }) {
  const ref = useRef(null);
  const reduit = useReducedMotion();
  const rotateX = useSpring(useMotionValue(0), springValues);
  const rotateY = useSpring(useMotionValue(0), springValues);
  const scale = useSpring(1, springValues);

  function handleMouse(e) {
    if (!ref.current || reduit) return;
    const rect = ref.current.getBoundingClientRect();
    const offsetX = e.clientX - rect.left - rect.width / 2;
    const offsetY = e.clientY - rect.top - rect.height / 2;
    rotateX.set((offsetY / (rect.height / 2)) * -rotateAmplitude);
    rotateY.set((offsetX / (rect.width / 2)) * rotateAmplitude);
  }

  return (
    <figure
      ref={ref}
      className={`tilted-card-figure ${className}`}
      style={style}
      onMouseMove={handleMouse}
      onMouseEnter={() => !reduit && scale.set(scaleOnHover)}
      onMouseLeave={() => {
        scale.set(1);
        rotateX.set(0);
        rotateY.set(0);
      }}
    >
      <motion.div className="tilted-card-inner" style={{ rotateX, rotateY, scale }}>
        {children}
      </motion.div>
    </figure>
  );
}
