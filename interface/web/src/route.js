// Routes dans le fragment de l'adresse : #/runs, #/run/<nom>/<onglet>?membre=...
import { useEffect, useState } from 'react';

function lireRoute() {
  const [chemin, requete] = window.location.hash.replace(/^#/, '').split('?');
  return {
    parties: chemin.split('/').filter(Boolean).map(decodeURIComponent),
    params: Object.fromEntries(new URLSearchParams(requete || ''))
  };
}

export function useRoute() {
  const [route, setRoute] = useState(lireRoute);
  useEffect(() => {
    const suivre = () => setRoute(lireRoute());
    window.addEventListener('hashchange', suivre);
    return () => window.removeEventListener('hashchange', suivre);
  }, []);
  return route;
}

export function lien(parties, params) {
  const chemin = '#/' + parties.filter(p => p !== undefined && p !== null && p !== '').map(encodeURIComponent).join('/');
  const requete = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString() : '';
  return requete ? `${chemin}?${requete}` : chemin;
}

// Ou suivre une tache en cours : le benchmark sur la page de son bot, le reste dans l'entrainement.
export const lienTache = t => (t?.type === 'benchmark' && t.run ? lien(['bots', t.run, 'benchmark']) : '#/entrainement');

export function aller(parties, params) {
  window.location.hash = lien(parties, params);
}
