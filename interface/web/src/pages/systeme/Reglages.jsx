// Reglages de l'interface, gardes dans ce navigateur : effets visuels et notifications.
import { useState } from 'react';
import { useDonnees } from '../../donnees.jsx';
import { BoutonDossier, Carte, EnTeteCarte } from '../../composants/Base.jsx';
import JellyRadio from '../../reactbits/JellyRadio/JellyRadio.jsx';

export default function Reglages() {
  const { effets, setEffets, notifications, setNotifications } = useDonnees();
  const [refus, setRefus] = useState(false);
  const basculerNotifications = async () => {
    if (notifications === 'oui') return setNotifications('non');
    if (!('Notification' in window)) return setRefus(true);
    const accord = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
    if (accord === 'granted') {
      setNotifications('oui');
      setRefus(false);
    } else setRefus(true);
  };
  return (
    <div className="grille grille-2">
      <Carte>
        <EnTeteCarte titre="Effets visuels" description="Les fonds animés du haut des pages, l’hélice, le mur des marchés, la carte du champion et le verdict se dessinent sur la GPU, celle-là même qui entraîne le bot." />
        <JellyRadio swell={0.14}
          className="rangee-jelly"
          value={effets}
          ariaLabel="Effets visuels"
          onChange={setEffets}
          items={[
            { value: 'auto', label: 'Automatique' },
            { value: 'oui', label: 'Toujours' },
            { value: 'non', label: 'Jamais' }
          ]}
        />
        <p className="discret">{{ auto: 'Coupés pendant une tâche : toute la GPU va au bot pendant qu’il travaille.', oui: 'Même pendant une tâche, au prix d’un peu de GPU prise au bot.', non: 'Aucun fond animé ; un dégradé calme les remplace.' }[effets]} Ils sont aussi coupés si le système demande moins d’animations.</p>
      </Carte>
      <Carte>
        <EnTeteCarte titre="Notifications du navigateur" description="Record de validation, fin ou échec d’une tâche, même quand l’onglet est caché." />
        <label className="interrupteur">
          <input type="checkbox" checked={notifications === 'oui'} onChange={basculerNotifications} />
          <span className="piste" />
          <span className="second">Prévenir quand l’onglet est caché</span>
        </label>
        <p className="discret">L’onglet garde alors sa connexion au serveur en arrière-plan.</p>
        {refus && <p className="discret">Le navigateur refuse les notifications : autorisez-les dans ses réglages pour ce site.</p>}
      </Carte>
      <Carte>
        <EnTeteCarte titre="Fichiers de l’interface" description="Tâches lancées, leurs sorties, les configurations des nouveaux bots et leurs noms : tout est dans interface/etat/, jamais dans un dossier de run." actions={<BoutonDossier cible="etat" libelle="Ouvrir" />} />
      </Carte>
    </div>
  );
}
