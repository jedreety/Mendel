// Lexique : chaque mot du bot, en une phrase ou deux, un a la fois. Une roue de mots (OptionWheel de React Bits) a
// gauche, sa definition a droite ; la molette, les fleches ou un clic changent de mot, la recherche y saute.
// ?terme=... ouvre un mot ; chaque terme souligne en pointille dans l'interface y renvoie.
import { useEffect, useMemo, useState } from 'react';
import { TERMES } from '../../glossaire.js';
import { Vide } from '../../composants/Base.jsx';
import OptionWheel from '../../reactbits/OptionWheel/OptionWheel.jsx';

const normaliser = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const TRIES = Object.entries(TERMES).sort(([, a], [, b]) => a.terme.localeCompare(b.terme, 'fr'));

export default function Lexique({ params }) {
  const [recherche, setRecherche] = useState('');
  const termes = useMemo(() => {
    const q = normaliser(recherche.trim());
    return q ? TRIES.filter(([, t]) => normaliser(`${t.terme} ${t.definition}`).includes(q)) : TRIES;
  }, [recherche]);
  const [choisi, setChoisi] = useState(() => Math.max(0, TRIES.findIndex(([id]) => id === params.terme)));
  // Un lien vers un mot (?terme=...) y mene, meme depuis cette page.
  useEffect(() => {
    const i = TRIES.findIndex(([id]) => id === params.terme);
    if (i < 0) return;
    setRecherche('');
    setChoisi(i);
  }, [params.terme]);
  const index = Math.max(0, Math.min(choisi, termes.length - 1));
  const [id, t] = termes[index] ?? [];

  return (
    <>
      <input
        className="saisie"
        style={{ maxWidth: 380 }}
        placeholder="Chercher un mot"
        value={recherche}
        onChange={e => {
          setRecherche(e.target.value);
          setChoisi(0);
        }}
        aria-label="Chercher dans le lexique"
      />
      {termes.length ? (
        <div className="lexique">
          <div className="lexique-roue">
            <OptionWheel
              key={recherche}
              items={termes.map(([, x]) => x.terme)}
              defaultSelected={index}
              selected={index}
              onChange={setChoisi}
              ariaLabel="Mots du lexique"
              fontSize={1.45}
              spacing={1.6}
              tilt={7}
              curve={1}
              blur={0.5}
              fade={0.16}
              minOpacity={0.06}
              inset={28}
              smoothing={160}
              loop
            />
          </div>
          {t && (
            <article className="lexique-definition" key={id}>
              <span className="oeil">
                {index + 1} sur {termes.length}
              </span>
              <h2>{t.terme}</h2>
              <p>{t.definition}</p>
              <span className="discret">Faites tourner la roue, ou utilisez les flèches du clavier.</span>
            </article>
          )}
        </div>
      ) : (
        <Vide titre="Aucun mot ne correspond" />
      )}
    </>
  );
}
