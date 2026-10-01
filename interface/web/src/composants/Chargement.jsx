// Ce qui se lit encore : une grille qui pulse et un verbe. Il n'apparait qu'apres un court delai, pour qu'une lecture
// rapide ne fasse pas clignoter la page.
import { useEffect, useState } from 'react';
import LatticeLoader from '../reactbits/LatticeLoader/LatticeLoader.jsx';

export default function Chargement({ texte = 'Lecture', delai = 220, minHauteur }) {
  const [visible, setVisible] = useState(delai === 0);
  useEffect(() => {
    if (delai === 0) return undefined;
    const minuterie = setTimeout(() => setVisible(true), delai);
    return () => clearTimeout(minuterie);
  }, [delai]);
  return (
    <div className="attente" style={minHauteur ? { minHeight: minHauteur, alignItems: 'center' } : undefined}>
      {visible && <LatticeLoader label={texte} pattern="orbit" grid={3} cellSize={5} gap={2} fontSize={13} showTimer={false} color="#8e8e96" />}
    </div>
  );
}
