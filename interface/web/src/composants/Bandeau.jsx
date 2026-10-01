// Le bandeau d'une section : son fond anime, en haut de page, fondu dans le blanc en bas. Chaque section a le sien,
// dans les memes tons pastel, a la meme place : ils se lisent comme une famille. Les fonds se dessinent sur la GPU
// qui entraine le bot : ils ne s'affichent que si les effets sont actifs (useEffetsActifs). Sinon, et pendant leur
// chargement, un degrade calme tient leur place. A chaque changement de section, l'ancien fond s'efface tout de suite
// et le nouveau n'arrive qu'apres la transition de page, pour qu'elle reste fluide.
import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffetsActifs } from '../donnees.jsx';
import { ACCENT, CYAN, PASTELS, VIOLET } from '../palette.js';
import Aurora from '../reactbits/Aurora/Aurora.jsx';
import GhostCursor from '../reactbits/GhostCursor/GhostCursor.jsx';
import SideRays from '../reactbits/SideRays/SideRays.jsx';
import ColorBends from '../reactbits/ColorBends/ColorBends.jsx';
import LaserFlow from '../reactbits/LaserFlow/LaserFlow.jsx';
import GradientBlinds from '../reactbits/GradientBlinds/GradientBlinds.jsx';
import LightRays from '../reactbits/LightRays/LightRays.jsx';

// Des tableaux stables : un nouveau tableau a chaque rendu relancerait certains fonds.
const AURORE = [PASTELS.bleu, PASTELS.lavande, PASTELS.ciel];
const COURBES = [ACCENT, VIOLET, CYAN, '#f28cc0'];
const STORES = ['#9cc2ff', '#c3b2ff', '#9fe3f2'];
// Chaque fond a sa force propre : on les ramene a une meme discretion sur le blanc.
const OPACITES = { aurore: 0.82, rayons: 1, courbes: 0.55, laser: 0.9, stores: 0.38, lumiere: 0.8 };

const FONDS = {
  aurore: () => (
    <>
      <Aurora colorStops={AURORE} amplitude={1.05} blend={0.6} speed={0.45} lightMode />
      <GhostCursor color="#6f9dff" brightness={1.6} trailLength={22} dpr={0.4} grainIntensity={0.03} />
    </>
  ),
  rayons: () => <SideRays origin="top-right" rayColor1={ACCENT} rayColor2={VIOLET} speed={1.3} intensity={2.2} spread={2} saturation={1.1} blend={0.5} falloff={1.4} opacity={0.7} />,
  courbes: () => <ColorBends colors={COURBES} rotation={100} speed={0.2} scale={2.4} frequency={1} warpStrength={1} mouseInfluence={0.6} parallax={0.4} noise={0.04} iterations={1} intensity={1.4} bandWidth={4.5} transparent />,
  laser: () => <LaserFlow lightMode color="#6f9bff" horizontalBeamOffset={0.3} verticalBeamOffset={-0.12} verticalSizing={1.8} horizontalSizing={0.36} fogIntensity={0.4} wispIntensity={3.5} wispDensity={0.9} flowSpeed={0.3} />,
  stores: () => <GradientBlinds gradientColors={STORES} angle={-14} noise={0.18} blindCount={14} blindMinWidth={80} spotlightRadius={0.6} spotlightSoftness={1.2} spotlightOpacity={0.6} mouseDampening={0.25} lightMode />,
  lumiere: () => <LightRays raysOrigin="top-center" raysColor="#5f9bff" raysSpeed={0.45} lightSpread={0.85} rayLength={1.35} fadeDistance={1.05} followMouse mouseInfluence={0.05} lightMode />
};

export default function Bandeau({ fond }) {
  const effets = useEffetsActifs();
  const [affiche, setAffiche] = useState(null);
  useEffect(() => {
    setAffiche(null);
    const minuterie = setTimeout(() => setAffiche(fond), 450);
    return () => clearTimeout(minuterie);
  }, [fond]);
  const Fond = effets && affiche ? FONDS[affiche] : null;
  return (
    <div className="bandeau" aria-hidden="true">
      <div className="bandeau-calme" />
      <AnimatePresence>
        {Fond && (
          <motion.div key={affiche} initial={{ opacity: 0 }} animate={{ opacity: OPACITES[affiche] ?? 1 }} exit={{ opacity: 0, transition: { duration: 0.3 } }} transition={{ duration: 0.9, ease: 'easeOut' }}>
            <Fond />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
