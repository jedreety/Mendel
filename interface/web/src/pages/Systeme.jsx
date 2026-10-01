// Systeme : tout le reste. Le poste, les taches, les donnees, le diagnostic, les reglages et le lexique ; les
// sous-pages sont dans le panneau lateral.
import { PAGES_SYSTEME } from '../navigation.js';
import { EnTete } from '../composants/Base.jsx';
import Poste from './systeme/Poste.jsx';
import Taches from './systeme/Taches.jsx';
import Donnees from './systeme/Donnees.jsx';
import Diagnostic from './systeme/Diagnostic.jsx';
import Reglages from './systeme/Reglages.jsx';
import Lexique from './systeme/Lexique.jsx';

const PAGES = { poste: Poste, taches: Taches, donnees: Donnees, diagnostic: Diagnostic, reglages: Reglages, lexique: Lexique };

export default function Systeme({ page, params }) {
  const Page = PAGES[page] ?? Poste;
  const info = PAGES_SYSTEME.find(p => p.cle === page) ?? PAGES_SYSTEME[0];
  return (
    <>
      <EnTete surtitre={<span className="oeil">Système</span>} titre={info.libelle} description={info.description} />
      <Page params={params} />
    </>
  );
}
