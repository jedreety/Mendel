// Icones au trait, sur une grille de 24 : elles remplacent Hugeicons dans les composants de React Bits.
const CHEMINS = {
  maison: 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  eclair: 'M13 2L4 14h7l-1 8 9-12h-7z',
  bot: 'M12 3v3M5 9a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3zM9.5 12h.01M14.5 12h.01M10 15.5h4',
  systeme: 'M4 5h16v11H4zM9 20h6M12 16v4',
  fleche: 'M5 12h14m-6-6l6 6-6 6',
  retour: 'M19 12H5m6 6l-6-6 6-6',
  coche: 'M20 6L9 17l-5-5',
  annuler: 'M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3',
  corbeille: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  crayon: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',
  rafraichir: 'M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5',
  chevron: 'M6 9l6 6 6-6',
  plus: 'M12 5v14M5 12h14',
  lecture: 'M8 5v14l11-7z',
  pause: 'M8 5h3v14H8zM13 5h3v14h-3z',
  stop: 'M7 7h10v10H7z',
  telecharger: 'M12 3v12m-5-5l5 5 5-5M4 20h16',
  dossier: 'M3 6h6l2 2h10v11H3z',
  horloge: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 4v5l3 3',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 8v5m0-8.5v.01',
  alerte: 'M12 3l10 18H2L12 3zm0 7v5m0 3v.01',
  croix: 'M6 6l12 12M18 6L6 18',
  verrou: 'M6 11h12v10H6zM8 11V7a4 4 0 1 1 8 0v4',
  ouvert: 'M6 11h12v10H6zM8 11V7a4 4 0 0 1 7.5-2',
  recherche: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16l-4.3-4.3',
  terminal: 'M4 17l6-6-6-6M12 19h8',
  graphique: 'M4 19V5M4 19h16M8 15l4-4 3 3 5-6',
  piece: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 4v10m2.5-7.5c0-1.1-1.1-2-2.5-2s-2.5.9-2.5 2 1.1 1.6 2.5 2 2.5.9 2.5 2-1.1 2-2.5 2-2.5-.9-2.5-2',
  boucle: 'M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3',
  cible: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  donnees: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  livre: 'M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z',
  pouls: 'M3 12h4l3-7 4 14 3-7h4',
  liste: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
  puce: 'M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4',
  reglages: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm0-6v3m0 12v3M4.2 4.2l2.1 2.1m11.4 11.4l2.1 2.1M3 12h3m12 0h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1',
  etincelle: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z',
  balance: 'M12 4v16M6 20h12M4 8h16M7 8l-3 7h6zM17 8l-3 7h6z',
  prisme: 'M12 3l9 16H3z',
  point: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  suivant: 'M5 5l9 7-9 7zM16 5h3v14h-3z',
  hausse: 'M7 17L17 7M9 7h8v8',
  baisse: 'M7 7l10 10M17 9v8H9'
};
const PLEINES = new Set(['eclair', 'lecture', 'pause', 'stop', 'point', 'suivant']);

export default function Icone({ nom, taille = 16, epaisseur = 1.9 }) {
  const plein = PLEINES.has(nom);
  return (
    <svg
      viewBox="0 0 24 24"
      width={taille}
      height={taille}
      fill={plein ? 'currentColor' : 'none'}
      stroke={plein ? 'none' : 'currentColor'}
      strokeWidth={epaisseur}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flex: 'none' }}
    >
      <path d={CHEMINS[nom] ?? CHEMINS.point} />
    </svg>
  );
}
