// Vocabulaire du bot evolutif. Chaque terme sert aux definitions au
// survol (composants/Aide.jsx) et a la page Glossaire.

export const TERMES = {
  generation: {
    terme: 'Génération',
    definition:
      'Un cycle complet de l’évolution : toute la population est évaluée sur le lot de fenêtres et notée, les meilleurs sont revus sur les fenêtres de confirmation, les 5 parents sont choisis puis validés, le Panthéon est mis à jour, les enfants naissent, et un point de sauvegarde est écrit.'
  },
  population: {
    terme: 'Population',
    definition: 'Le nombre de bots évalués à chaque génération, 10 240 par défaut. Les 5 parents y entrent tels quels ; tous les autres sont leurs enfants.'
  },
  bot: {
    terme: 'Bot',
    definition:
      'Un réseau récurrent de 64 neurones qui lit ses 80 modules de signal, résumés en 8 canaux, et 18 valeurs d’état, et décide à chaque heure d’acheter, de vendre ou de conserver. Tous ses paramètres sont des gènes.'
  },
  genome: {
    terme: 'Génome',
    definition: 'Les 8 050 gènes d’un bot : 6 919 pour le réseau, dont 640 pour résumer les modules en canaux, 960 pour l’adaptation, 161 pour les modules, 6 pour la décision et 4 amplitudes de mutation.'
  },
  modules: {
    terme: 'Modules de signal',
    definition:
      'Les 8 modules d’origine (première bougie, croisement de moyennes, RSI, cassure, momentum, volatilité relative, volume relatif, retour à la moyenne) et les 72 règles du moteur : bougies, séances, tendance, retour à la moyenne, volume. Tous sont toujours allumés ; chacun produit un signal entre −1 et 1 et, sauf ceux des séances, a son échelle : 1, 4 ou 24 heures. Le réseau apprend lesquels écouter.'
  },
  lot: {
    terme: 'Lot de fenêtres',
    definition:
      '4 fenêtres de 90 jours tirées au hasard dans le bloc d’entraînement, sans chevauchement. Tous les bots d’une génération voient le même lot, avec les mêmes frais et le même glissement. Le lot change une fenêtre à la fois : toutes les 5 générations, la plus ancienne est remplacée, et chaque fenêtre sert 20 générations.'
  },
  prechauffage: {
    terme: 'Préchauffage',
    definition: 'Les 30 jours qui précèdent chaque fenêtre et chaque trimestre : les barres y alimentent les indicateurs et le réseau, mais aucun ordre n’est passé.'
  },
  blocs: {
    terme: 'Blocs de temps',
    definition: 'Chaque bot a les siens : les années d’entraînement, puis une année de validation découpée en 4 trimestres, puis le test jusqu’à la dernière barre. Par défaut : 2020 à 2023, 2024, puis 2025. Des tampons d’un mois les séparent.'
  },
  tampon: {
    terme: 'Tampon',
    definition: 'Le mois qui précède un bloc. Il sert de préchauffage au bloc suivant et n’est noté par aucun bloc : aucune barre notée ne passe d’un bloc à l’autre.'
  },
  noteEntrainement: {
    terme: 'Note d’entraînement',
    definition:
      'Pour chaque fenêtre, la croissance du capital en logarithme, frais compris, moins 5 fois le carré de la pire chute. La note vaut 0,7 × la moyenne des fenêtres + 0,3 × la moins bonne ; un gain y est réduit tant qu’assez de trades ne le prouvent pas. 0,05 vaut à peu près +5 % par fenêtre de 90 jours ; un bot qui ne trade pas a −0,10.'
  },
  noteValidation: {
    terme: 'Note de validation',
    definition:
      'La même formule sur les 4 trimestres de l’année de validation, aux coûts de référence. C’est elle qui décide du Panthéon et du champion.'
  },
  composantes: {
    terme: 'Composantes de la note',
    definition:
      'La croissance du capital ; la pénalité de chute, qui grandit comme le carré de la pire chute (10 % en efface 5,5 %, 20 % en efface 25 %) ; la preuve, ce que le manque de trades retire à un gain ; l’activité, la pénalité d’un bot qui trade trop peu. Leur somme est la note.'
  },
  preuve: {
    terme: 'Preuve',
    definition:
      'Un gain ne compte en entier que s’il est appuyé par assez de trades : il est multiplié par n / (n + 10 par fenêtre). Avec 40 trades sur 4 fenêtres, il compte à moitié ; avec 360, à 90 %. Une perte compte toujours en entier.'
  },
  inactivite: {
    terme: 'Inactivité',
    definition: 'Un bot qui trade en moyenne moins de 5 fois par fenêtre perd une part de 0,10 : toute la pénalité s’il ne trade pas, rien à partir de 5 trades par fenêtre.'
  },
  confirmation: {
    terme: 'Confirmation',
    definition:
      'Les 200 meilleurs de chaque génération, et les parents en place, sont revus sur les fenêtres qui viennent de sortir du lot. Les parents sont choisis sur le lot et la confirmation : un bot doit tenir sur 8 fenêtres, pas sur 4, et ne perd pas ce qu’il a appris quand une fenêtre change.'
  },
  parents: {
    terme: 'Parents',
    definition:
      'Les 5 bots de meilleure note confirmée, deux à deux distincts : un candidat est écarté si ses positions sont corrélées à plus de 0,90 avec celles d’un parent déjà retenu. Le meilleur a le plus d’enfants : 46 %, puis 27 %, 16 %, 8 % et 2,5 %.'
  },
  elitisme: {
    terme: 'Élitisme',
    definition: 'Les parents passent sans changement dans la génération suivante, où ils sont réévalués avec les autres.'
  },
  enfant: {
    terme: 'Enfant',
    definition: 'Un parent muté. Il est défini par l’indice de son parent et une graine : tout bot évalué peut être reconstruit et rejoué à l’identique.'
  },
  sigma: {
    terme: 'Amplitude de mutation (σ)',
    definition:
      'Chaque groupe de gènes (modules, réseau, décision, adaptation) porte sa propre amplitude, elle-même héritée et mutée avant les autres gènes, entre le quart et le quadruple de sa valeur de départ. À chaque naissance, l’enfant tire en plus sa force, de 0,1 à 10 fois l’amplitude, et chacun de ses gènes son ampleur, de 0,001 à 4 fois : la plupart bougent à peine, quelques-uns font un grand saut.'
  },
  pantheon: {
    terme: 'Panthéon',
    definition:
      'Les 5 meilleures notes de validation obtenues depuis le début du run, deux à deux distinctes. Chaque nouvel entrant est rejoué dans le moteur exact avant d’être retenu. À l’arrêt, le Panthéon est rejoué et journalisé dans pantheon/.'
  },
  champion: {
    terme: 'Champion',
    definition: 'Le premier du Panthéon : la meilleure note de validation du run. C’est lui qui passe le benchmark final.'
  },
  championAleatoire: {
    terme: 'Champion aléatoire',
    definition: 'Le meilleur bot de la génération 0, tirée au hasard, choisi par sa note d’entraînement : ce que donne le hasard sans aucune évolution.'
  },
  stagnation: {
    terme: 'Stagnation',
    definition: 'Le nombre de générations depuis le dernier progrès du Panthéon. Un run réel s’arrête de lui-même quand elle atteint stagnation_max, 100 par défaut.'
  },
  pointSauvegarde: {
    terme: 'Point de sauvegarde',
    definition: 'etat.json, écrit à chaque génération. Un run arrêté reprend exactement là, et redonne les mêmes fichiers qu’un run continu.'
  },
  rejeuExact: {
    terme: 'Rejeu exact',
    definition:
      'Le flux d’ordres calculé sur la GPU, rejoué dans le grand livre du moteur, en décimal exact, par le courtier simulé. Il doit redonner les mêmes capitaux à 0,1 % près ; en pratique, sans aucun écart.'
  },
  runReel: {
    terme: 'Run réel',
    definition: 'Un entraînement sur les vrais prix. Ses témoins, le run à blanc et la recherche aléatoire, mesurent ce qu’il vaut contre le hasard.'
  },
  aBlanc: {
    terme: 'Run à blanc',
    definition:
      'Le même entraînement, avec les mêmes graines et le même nombre de générations, sur des prix permutés année par année : il n’y a rien à apprendre. La note de son champion est la note du hasard.'
  },
  hasard: {
    terme: 'Recherche aléatoire',
    definition: 'Le même budget d’évaluations que le run réel, mais chaque génération tirée au hasard, sans évolution. Elle est facultative.'
  },
  ecartHasard: {
    terme: 'Écart au hasard',
    definition: 'La note de validation du champion réel moins celle du champion à blanc. Au-dessus de zéro, l’évolution a trouvé plus que du bruit.'
  },
  blocTest: {
    terme: 'Bloc de test',
    definition: 'De 2025 à la dernière barre. Jamais lu pendant l’entraînement, et ouvert une seule fois, par le benchmark final.'
  },
  benchmark: {
    terme: 'Benchmark final',
    definition:
      'Le champion et les références (buy and hold, champion aléatoire, champion à blanc, recherche aléatoire) passent le bloc de test, trimestre par trimestre. Le dossier benchmark/ sert de verrou : rien n’est jamais relancé.'
  },
  dsr: {
    terme: 'Deflated Sharpe Ratio',
    definition:
      'La probabilité que le Sharpe du champion soit réel, corrigée du nombre de bots essayés en validation : plus on essaie de bots, plus un bon Sharpe peut venir du seul hasard.'
  },
  psr: {
    terme: 'Probabilistic Sharpe Ratio',
    definition: 'La probabilité que le vrai Sharpe dépasse zéro, compte tenu de la longueur de la série, de son asymétrie et de ses queues.'
  },
  sharpe: {
    terme: 'Sharpe annualisé',
    definition: 'La moyenne des rendements horaires du capital divisée par leur écart-type, multipliée par √8 760.'
  },
  seuilAction: {
    terme: 'Seuil d’action',
    definition: 'Un gène entre 0,34 et 0,95. Le bot n’agit que si la probabilité de l’action la plus probable le dépasse ; sinon il conserve.'
  },
  stopPrise: {
    terme: 'Stop et prise de gain',
    definition:
      'Posés à chaque clôture pour la barre suivante, à C − k_stop × ATR et C + k_tp × ATR, en ordres au repos. Le stop ne descend jamais sous 95 % du prix d’entrée. S’ils sont touchés dans la même barre, le stop est retenu.'
  },
  dureeMax: {
    terme: 'Durée maximale',
    definition: 'Fixée à l’ouverture par le réseau, de 1 à 240 barres : quand elle est atteinte, la position est fermée au marché.'
  },
  adaptation: {
    terme: 'Adaptation en cours de vie',
    definition:
      'À la fermeture d’un trade, le bot modifie les poids qui relient ses neurones cachés à ses scores d’action, selon une règle que l’évolution fixe. Les poids reviennent à leur valeur de naissance à chaque fenêtre.'
  },
  noyau: {
    terme: 'Noyau CUDA',
    definition:
      'Le simulateur GPU, compilé au lancement, qui fait avancer tous les bots d’un paquet barre par barre. Son empreinte est notée : un run repris avec d’autres noyaux ne redonne pas un run continu.'
  },
  paquet: {
    terme: 'Paquet',
    definition: 'Un groupe de bots simulés ensemble sur la GPU. Sa taille est calibrée au lancement : sous 60 % de la mémoire et sous 16 384 bots.'
  },
  populationReference: {
    terme: 'Population de référence',
    definition: '10 000 bots tirés comme la génération 0, avec leur propre graine. Le benchmark situe la note de test du champion parmi les leurs.'
  },
  graine: {
    terme: 'Graine maîtresse',
    definition: 'Tous les tirages en dérivent. Même configuration et même graine donnent le même Panthéon, au bit près.'
  },
  trimestre: {
    terme: 'Trimestre',
    definition: 'La validation et le test sont découpés en trimestres civils ; chacun joue le rôle d’une fenêtre, avec 1 000 USDT au départ et 30 jours de préchauffage.'
  }
};

// Description de chaque parametre de evolution/config.toml.
export const PARAMETRES = {
  donnees: 'Fichier des barres horaires : time, open, high, low, close, volume.',
  debut_entrainement: 'Début du bloc d’entraînement, où les fenêtres sont tirées.',
  debut_validation: 'Début de la validation, en 4 trimestres. Le mois qui précède sert de tampon.',
  debut_test: 'Début du bloc de test, jamais lu pendant l’entraînement.',
  fenetres_par_lot: 'Fenêtres d’entraînement par lot, communes à tous les bots.',
  duree_fenetre_jours: 'Durée notée d’une fenêtre d’entraînement, en jours.',
  prechauffage_jours: 'Préchauffage avant chaque fenêtre et chaque trimestre ; aussi la durée des tampons.',
  renouvellement_lot: 'Générations pendant lesquelles une fenêtre reste dans le lot ; une fenêtre change à chaque fraction de cette durée.',
  capital_initial: 'Argent fictif dont chaque bot dispose au départ de chaque fenêtre et de chaque trimestre.',
  frais_entrainement: 'Bornes du tirage des frais par côté, pour chaque fenêtre d’entraînement.',
  glissement_entrainement: 'Bornes du tirage du glissement par côté, pour chaque fenêtre d’entraînement.',
  frais_reference: 'Frais par côté en validation et en test.',
  glissement_reference: 'Glissement par côté en validation et en test.',
  pas_de_prix: 'Plus petit écart entre deux prix sur ce marché (PRICE_FILTER chez Binance).',
  pas_de_quantite: 'Plus petit écart entre deux quantités achetées (LOT_SIZE chez Binance).',
  notionnel_minimum: 'Plus petit ordre accepté, dans la monnaie de cotation (NOTIONAL chez Binance).',
  taille_cachee: 'Neurones de la couche cachée du réseau. Change la taille du génome.',
  canaux_modules: 'Entrées du réseau qui résument les signaux des 80 modules. Au-delà de 8, le simulateur ralentit.',
  duree_max_barres: 'Durée maximale de détention d’une position, en barres horaires.',
  adaptation_en_vie: 'Le bot modifie ses poids de décision d’après ses trades.',
  population: 'Bots évalués par génération. La durée d’une génération lui est à peu près proportionnelle.',
  nb_parents: 'Parents retenus à chaque génération ; aussi la taille du Panthéon.',
  seuil_distinction: 'Corrélation des positions au-delà de laquelle deux bots sont tenus pour identiques.',
  candidats_examines: 'Meilleurs bots examinés pour choisir les parents distincts.',
  sigma_initial_reseau: 'Amplitude de mutation initiale du groupe réseau.',
  sigma_initial_autres: 'Amplitude de mutation initiale des groupes modules, décision et adaptation.',
  amplitude_marge: 'Chaque amplitude s’adapte entre sa valeur initiale divisée et multipliée par ce facteur : elle ne peut ni geler ses gènes, ni les disperser.',
  mutation_enfant: 'Bornes de la force tirée par chaque enfant, en multiple de l’amplitude de ses groupes : certains changent à peine, d’autres beaucoup.',
  mutation_gene: 'Bornes de l’ampleur tirée par chaque gène d’un enfant : la plupart bougent très peu, quelques-uns sautent.',
  proba_categoriel: 'Probabilité de retirer un gène catégoriel, comme une échelle ou un type de moyenne.',
  graine_maitresse: 'Graine dont dérivent tous les tirages : même graine, même Panthéon.',
  penalite_chute: 'Une fenêtre perd ce nombre fois le carré de sa pire chute, en logarithme : à 5, une chute de 10 % efface 5,5 % de croissance.',
  trades_preuve: 'Trades par fenêtre avec lesquels un gain ne compte qu’à moitié : plus il y en a, plus il faut de trades pour prouver un gain.',
  trades_minimum: 'Trades par fenêtre, en moyenne, en dessous desquels la pénalité d’inactivité s’applique.',
  penalite_inactivite: 'Pénalité d’un bot qui ne trade pas ; elle diminue jusqu’à zéro avec ses trades.',
  seuil_ruine: 'Capital sous lequel un trimestre est marqué ruiné dans le bilan, en fraction du départ.',
  agregation: 'Poids de la moyenne et de la moins bonne fenêtre dans la note finale.',
  population_reference: 'Bots aléatoires parmi lesquels le benchmark situe la note de test du champion.',
  memoire_gpu_max: 'Part de la mémoire de la GPU que les paquets peuvent occuper.',
  stagnation_max: 'Générations sans progrès du Panthéon avant l’arrêt automatique ; 0 le désactive.',
  generations_max: 'Arrêt après ce nombre de générations ; 0 : pas de limite, arrêt par Ctrl+C ou sur stagnation.',
  tolerance_rejeu: 'Écart toléré entre la GPU et le rejeu exact, en fraction du capital initial.'
};
