// Acces a l'API du serveur Python (interface/serveur.py).

export async function lire(url) {
  const reponse = await fetch(url);
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(donnees.erreur || `${reponse.status} ${reponse.statusText}`);
  return donnees;
}

// Toute commande porte l'en-tete X-Interface : le serveur refuse celles qui ne l'ont pas.
export async function envoyer(url, corps) {
  const reponse = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Interface': '1' },
    body: JSON.stringify(corps ?? {})
  });
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(donnees.erreur || `${reponse.status} ${reponse.statusText}`);
  return donnees;
}

export const enc = encodeURIComponent;
