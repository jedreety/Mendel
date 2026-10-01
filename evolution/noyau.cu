// Noyau CUDA du simulateur (ARCHITECTURE.md, section 21.8), compile a l'execution par NVRTC.
//
// evolution/noyau.py place avant ce texte les constantes (H, E, W, NMOD, CANAUX, NG, GMAX, les indices des
// descripteurs), puis y insere les fonctions de signal des modules et leur aiguillage. Les reglages de la
// configuration et le mode de trace sont aussi des constantes (ADAPTATION, TRACE, COMPLET, DUREE_BARRES,
// NOTIONNEL_MIN, SEUIL_RUINE, PAS_DE_PRIX) : un noyau par mode, sans le code qu'il n'execute pas.
//
// Un bloc par bot, H fils. Le fil t porte le neurone cache t pour les W fenetres du bot a la fois : sa
// colonne de poids et ses poids de sortie restent dans ses registres pendant tout l'appel, et chaque poids lu
// sert aux W fenetres. Le reste, etat des couloirs compris, est en memoire partagee : les registres limitent
// le nombre de blocs qu'un SM fait avancer ensemble, donc la latence qu'il peut cacher. Les fils 0 a W - 1,
// les meneurs, tiennent chacun les comptes d'une fenetre. Ils sont dans le meme warp : les W comptes avancent
// ensemble, et ce warp calcule en parallele, un rapport ou une sortie par fil, ce qui peut l'etre. Les barres
// du marche et les signaux des modules, qui ne dependent pas de l'etat du bot, sont lus d'avance par tous les
// fils, AVANCE barres a la fois, et resumes en CANAUX entrees du reseau par la projection du bot. Tout se
// calcule dans un ordre fixe, bot par bot : le resultat d'un bot ne depend ni de la taille du paquet ni de sa
// place dans le paquet.
//
// Comptabilite exacte en entiers de 64 bits : prix en pas de prix, quantites en pas de quantite, montants
// en unites de pas de prix x pas de quantite / 1 000 000, arrondis du lieu d'execution du moteur. Le double,
// 64 fois plus lent que le simple sur les cartes grand public, est reserve aux prix des protections, au
// dimensionnement, aux resultats des trades et aux moments : les entrees du reseau se calculent en simple.

typedef long long i64;
typedef unsigned long long u64;

#define MILLION 1000000LL
#define PLANCHER 5
#define R_STOP 0
#define R_CIBLE 1
#define R_DUREE 2
#define R_VENTE 3
#define R_FIN 4
#define D_RIEN 0
#define D_OUVERTURE 1
#define D_PROTECTION 2
#define D_FERMETURE 3
#define EH (E + H)
#define ETATS (E - CANAUX)   // entrees d'etat du reseau, apres les canaux
#define NTRACE (NMOD + ETATS)  // entrees tracees : les signaux des modules, puis l'etat
#define QUANTUM ((float)(1.0 / 127.0))       // pas des tables a 8 bits, comme marche.py
#define INDEFINI (-128)                      // valeur a 8 bits qui n'est pas definie
#define QUANTUM16 ((float)(1.0 / 32767.0))   // de meme sur 16 bits
#define INDEFINI16 (-32768)
#define WP 4         // fenetres d'un bot, completees a 4 : les valeurs d'une entree tiennent dans un float4
#define NW (H / 32)  // warps du bloc
#define NS 7         // sorties d'une fenetre : scores d'acheter, de vendre, de conserver, taille, stop, prise de
                     // gain, duree
#define AVANCE 16    // barres lues d'avance
#define BLOCS_PAR_SM 6  // blocs residents vises : le compilateur tient les registres sous 65536 / (6 H)
#define NETAT 20
#define PAS_F ((float)PAS_DE_PRIX)
#define INV_PAS (1.0 / PAS_DE_PRIX)

// Champs entiers de l'etat d'un couloir, dans l'ordre de simulator.ENTIERS.
enum { CASH, QTE, PRIX_ENTREE, FRAIS_ENTREE, RISQUE0, CAPITAL_OUV, DUREE, DUREE_MAX, STOP, CIBLE, JOUR_REF, PIC,
       FRAIS_CUM, CAPITAL_PREC, NB, GAGNANTS, FRAIS_TOTAL, ROTATION, DD_FIN, DD_PIC };
// Champs en double : resultats des trades, drawdown, moments des rendements horaires.
enum { SOMME_R, SOMME_R2, DD, M1, M2, M3, M4 };

struct Marche {
    const i64* indices;
    const i64* local;
    const float* cloture;
    const float* volume;
    const float* moyennes;        // moyennes glissantes de n barres, ligne n - 1
    const float* ecarts_types;
    const float* volumes_moyens;
    const float* atr;
    const float* max_haut;
    const float* min_bas;
    const i64* niveau_de;
    const float* ouverture_c;     // ouverture, plus haut et plus bas des trois echelles, bout a bout
    const float* haut_c;
    const float* bas_c;
    const float* volatilites;     // R des regles du moteur, periodes 1 a VOLATILITE_MAX : ligne n - 1
    const float* ema;             // moyennes exponentielles, periodes 2 a 400 : ligne n - 2
    const double* somme_typique;  // sommes cumulees par echelle, precedees d'un zero
    const double* somme_pression;
    const i64* segment;           // echelle de chaque place de l'axe combine
    const unsigned char* heure;   // heure et jour de la semaine de la cloture de chaque barre horaire
    const unsigned char* jour;
    const float* tables[NTABLES > 0 ? NTABLES : 1];  // tables des modules ; celles a 8 bits sont relues en octets
    int n1;
    int ncomb;
    // Barres horaires, pour la lecture d'avance du noyau.
    const i64* ouv;
    const i64* haut;
    const i64* bas;
    const i64* clo;
    const float4* temps;
    const unsigned char* minuit;
};

__device__ __forceinline__ float nan_f() { return __int_as_float(0x7fc00000); }

// Maximum avec 0 qui garde NaN, comme clamp(min=0) de PyTorch.
__device__ __forceinline__ float positif(float x) { return x < 0.f ? 0.f : x; }

__device__ __forceinline__ float diviser(float a, float b) { return b > 0.f ? a / b : nan_f(); }

__device__ __forceinline__ int indice(const Marche& m, int echelle, int i) {
    return (int)m.indices[(i64)echelle * m.n1 + i];
}

__device__ __forceinline__ bool valide(const Marche& m, int j, int n) { return j >= 0 && m.local[j] >= n - 1; }

__device__ __forceinline__ float cloture_en(const Marche& m, int j) { return j >= 0 ? m.cloture[j] : nan_f(); }

__device__ __forceinline__ float cloture_avant(const Marche& m, int n, int j) {
    return valide(m, j, n + 1) ? m.cloture[j - n] : nan_f();
}

__device__ __forceinline__ float atr_en(const Marche& m, int p, int j) {
    return j >= 0 ? m.atr[(i64)(p - 1) * m.ncomb + j] : nan_f();
}

// Moyennes, ecarts-types et volumes moyens glissants : tables de marche.py, NaN la ou l'historique ne suffit pas.
__device__ __forceinline__ float glissante(const Marche& m, const float* table, int n, int j) {
    return j >= 0 ? table[(i64)(n - 1) * m.ncomb + j] : nan_f();
}

__device__ __forceinline__ float moyenne_simple(const Marche& m, int n, int j) { return glissante(m, m.moyennes, n, j); }

__device__ __forceinline__ float ecart_type(const Marche& m, int n, int j) { return glissante(m, m.ecarts_types, n, j); }

__device__ __forceinline__ float volume_en(const Marche& m, int j) { return j >= 0 ? m.volume[j] : nan_f(); }

__device__ __forceinline__ float volume_moyen(const Marche& m, int n, int j) {
    return glissante(m, m.volumes_moyens, n, j);
}

__device__ float extreme(const Marche& m, const float* table, bool maximum, int n, int j) {
    const int k = (int)m.niveau_de[n];
    const i64 base = (i64)k * m.ncomb;
    const int jj = j < 0 ? 0 : j;
    i64 autre = (i64)j - n + (1LL << k);
    if (autre < 0) autre = 0;
    const float a = table[base + jj], b = table[base + autre];
    const float r = maximum ? fmaxf(a, b) : fminf(a, b);
    return valide(m, j, n) ? r : nan_f();
}

__device__ __forceinline__ float plus_haut(const Marche& m, int n, int j) { return extreme(m, m.max_haut, true, n, j); }

__device__ __forceinline__ float plus_bas(const Marche& m, int n, int j) { return extreme(m, m.min_bas, false, n, j); }

__device__ __forceinline__ float sigmoide(float x) { return 1.f / (1.f + expf(-x)); }

// Outils des regles du moteur (evolution/modules/regles), comme les accesseurs de marche.py.
__device__ __forceinline__ float octet(const float* table, i64 k) {
    const signed char q = ((const signed char*)table)[k];
    return q == INDEFINI ? nan_f() : (float)q * QUANTUM;
}

__device__ __forceinline__ float lire8(const Marche& m, int t, int ligne, int j) {
    return j >= 0 ? octet(m.tables[t], (i64)ligne * m.ncomb + j) : nan_f();
}

__device__ __forceinline__ float lire16(const Marche& m, int t, int ligne, int j) {
    if (j < 0) return nan_f();
    const short q = ((const short*)m.tables[t])[(i64)ligne * m.ncomb + j];
    return q == INDEFINI16 ? nan_f() : (float)q * QUANTUM16;
}

__device__ __forceinline__ float lire8_horaire(const Marche& m, int t, int ligne, int i) {
    return octet(m.tables[t], (i64)ligne * m.n1 + i);
}

__device__ __forceinline__ float en(const float* serie, int j) { return j >= 0 ? serie[j] : nan_f(); }

__device__ __forceinline__ float precedente(const Marche& m, const float* serie, int j) {
    return valide(m, j, 2) ? serie[j - 1] : nan_f();
}

__device__ __forceinline__ float volatilite(const Marche& m, int n, int j) {
    return j >= 0 ? m.volatilites[(i64)(n - 1) * m.ncomb + j] : nan_f();
}

__device__ __forceinline__ float ema_en(const Marche& m, int n, int j) {
    return j >= 0 ? m.ema[(i64)(n - 2) * m.ncomb + j] : nan_f();
}

// Somme des n dernieres valeurs d'une serie cumulee, jusqu'a j, en double ; j valide.
__device__ __forceinline__ double fenetre64(const Marche& m, const double* table, int n, int j) {
    const i64 position = (i64)j + m.segment[j] + 1;
    const i64 debut = position - n;
    return table[position] - table[debut < 0 ? 0 : debut];
}

// min(1, x), NaN compris ; et le signe, 0 pour 0.
__device__ __forceinline__ float plafond(float x) { return x > 1.f ? 1.f : x; }

__device__ __forceinline__ float signe(float x) { return x > 0.f ? 1.f : (x < 0.f ? -1.f : 0.f); }

// Oscillateur de 0 a 100 lu en retour a la moyenne, comme regles/commun.py : sous bas +1, au-dessus de haut -1.
__device__ __forceinline__ float seuils(float x, float bas, float haut) {
    if (x < bas) return (bas - x) / bas;
    if (x > haut) return -((x - haut) / (100.f - haut));
    return 0.f;
}

__device__ __forceinline__ float lire_oscillateur(const Marche& m, int t, int ligne, int j) {
    return __fadd_rn(50.f, __fmul_rn(50.f, lire8(m, t, ligne, j)));  // sans FMA, comme PyTorch
}

/*MODULES*/

__device__ __forceinline__ float signal_module(const Marche& m, int module, const float* g, int i, int periode_atr) {
    switch (module) {
/*AIGUILLAGE*/
    }
    return 0.f;
}

// Regle d'adaptation a cinq coefficients (section 21.5), eta deja integre aux coefficients.
__device__ __forceinline__ float adapter(float poids, float r, float h, float y, float a, float b, float c, float d) {
    const float v = poids + r * (a * h * y + b * h + c * y + d);
    return fminf(fmaxf(v, -5.f), 5.f);
}

// Composante w d'un float4 ; w est connu a la compilation une fois les boucles deroulees.
__device__ __forceinline__ float composante(const float4& v, int w) {
    return w == 0 ? v.x : (w == 1 ? v.y : (w == 2 ? v.z : v.w));
}

// Etat des couloirs d'un bot, en memoire partagee : un tableau par champ, une case par fenetre.
struct Couloirs {
    i64 e[NETAT][WP];
    double f[7][WP];
    i64 sorties[5][WP];
    float derniers[5][WP];
    int ruine[WP];
    i64 anneau[24][WP];  // frais cumules a la fin de chacune des 24 dernieres barres
};

// Les champs entiers d'un couloir : c[CASH], c[QTE]...
struct Champs {
    i64* p;
    __device__ __forceinline__ i64& operator[](int champ) const { return p[champ * WP]; }
};

// Vend toute la position a prix. Renvoie r, le resultat net en multiples du risque initial.
__device__ float fermer(Couloirs& s, int w, i64 prix, int raison, i64 frais_ppm) {
    const Champs c{&s.e[0][w]};
    const i64 q = c[QTE];
    const i64 brut = prix * q * MILLION;
    const i64 frais = prix * q * frais_ppm;
    const i64 net = (prix - c[PRIX_ENTREE]) * q * MILLION - c[FRAIS_ENTREE] - frais;
    c[CASH] += brut - frais;
    c[QTE] = 0;
    c[NB] += 1;
    if (net > 0) c[GAGNANTS] += 1;
    const double r_capital = (double)net / (double)(c[CAPITAL_OUV] > 1 ? c[CAPITAL_OUV] : 1);
    s.f[SOMME_R][w] += r_capital;
    s.f[SOMME_R2][w] += r_capital * r_capital;
    double r = (double)net / (double)(c[RISQUE0] > 1 ? c[RISQUE0] : 1);
    r = r < -3.0 ? -3.0 : (r > 3.0 ? 3.0 : r);
    for (int q2 = 4; q2 > 0; --q2) s.derniers[q2][w] = s.derniers[q2 - 1][w];
    s.derniers[0][w] = (float)r;
    s.sorties[raison][w] += 1;
    c[FRAIS_TOTAL] += frais;
    c[FRAIS_CUM] += frais;
    c[ROTATION] += brut;
    return (float)r;
}

// a / b < f / p pour des entiers positifs, b et p non nuls : produits croises exacts, sur 128 bits.
__device__ __forceinline__ bool plus_petit(i64 a, i64 b, i64 f, i64 p) {
    const u64 h1 = __umul64hi((u64)a, (u64)p), h2 = __umul64hi((u64)f, (u64)b);
    return h1 < h2 || (h1 == h2 && (u64)a * (u64)p < (u64)f * (u64)b);
}

// Drawdown maximal d'apres la barre qui le realise : 1 - capital / pic, comme le moteur.
__device__ __forceinline__ double drawdown(i64 fin, i64 pic) { return pic > 0 ? 1.0 - (double)fin / (double)pic : 0.0; }

template <typename T> __device__ __forceinline__ T* pointeur(const i64* d, int k) { return (T*)(d[k]); }

// Pointeur relu dans un descripteur a chaque usage : le compilateur ne le garde pas en registre d'un bout a
// l'autre de l'appel, ou il ne sert qu'au debut, a la fin ou rarement.
template <typename T> __device__ __forceinline__ T* relu(const i64* d, int k) {
    return (T*)(((volatile const i64*)d)[k]);
}

// Reglages du paquet qui ne sont pas des constantes de compilation, en memoire partagee : relus apres chaque
// barriere, ils n'occupent pas de registres.
struct Reglages {
    int Lt, periode_atr, B;
};

// Une etape du repli des sommes sur le warp : les 2 ECART valeurs de s se reduisent a ECART. Le fil dont le
// bit ECART est a 1 garde la moitie haute, son voisin la moitie basse, et chacun recoit la moitie qu'il garde.
// ECART est une constante : s reste en registres.
template <int ECART> __device__ __forceinline__ void replier(float* s, int lane) {
    const bool dessus = (lane & ECART) != 0;
    #pragma unroll
    for (int q = 0; q < ECART; ++q) {
        const float envoi = dessus ? s[q] : s[q + ECART];
        s[q] = (dessus ? s[q + ECART] : s[q]) + __shfl_xor_sync(0xffffffffu, envoi, ECART);
    }
}

// Adaptation des trois poids d'action du neurone t dans la fenetre w apres un trade de resultat r (section
// 21.5). Les coefficients, lus rarement, restent en memoire globale : (coefficient, bot, neurone, action).
__device__ __forceinline__ void adapter_fenetre(float (*sWa)[3][H], const float (*sHo)[H], const float (*sYo)[4],
                                                const i64* P, int B, int bot, int t, int w, float r) {
    const float* ad = relu<const float>(P, P_ADAPT);
    const i64 coefficient = (i64)B * H * 3;
    for (int j = 0; j < 3; ++j) {
        const i64 x = ((i64)bot * H + t) * 3 + j;
        sWa[w][j][t] = adapter(sWa[w][j][t], r, sHo[w][t], sYo[w][j], ad[x], ad[x + coefficient],
                               ad[x + 2 * coefficient], ad[x + 3 * coefficient]);
    }
}

extern "C" __global__ void __launch_bounds__(H, BLOCS_PAR_SM) simuler(const i64* __restrict__ M,
                                                                     const i64* __restrict__ P, int k0, int pas) {
    __shared__ Marche sM;                   // relus apres chaque barriere : ni le marche ni les reglages
    __shared__ Reglages sReg;               // n'occupent de registres
    __shared__ float4 sX[ETATS];            // entrees d'etat ; composante w : fenetre w
    __shared__ float4 sH[2][H];             // etat cache, en double tampon : une barre lit l'un, ecrit l'autre
    __shared__ float4 sCh[AVANCE][CANAUX];  // canaux des barres lues d'avance : signaux des modules projetes
    __shared__ i64 sOuv[AVANCE][WP], sHaut[AVANCE][WP], sBas[AVANCE][WP], sClo[AVANCE][WP];
    __shared__ float4 sTemps[AVANCE][WP];
    __shared__ float sAtr[AVANCE][WP];      // ATR horaire du bot
    __shared__ int sMinuit[AVANCE][WP];
    __shared__ float sPart[NW][32];         // sommes des sorties par warp : fenetre w, sortie j en w * NS + j
    __shared__ float sG[NG];                // genes des modules
    __shared__ float sWa[WP][3][H];         // poids d'action du neurone t dans la fenetre w, modifies pendant la vie
    __shared__ float sHo[WP][H];            // etat cache a l'ouverture de la position en cours
    __shared__ float sBiais[NS];            // biais des scores d'action, puis des quatre sorties
    __shared__ float sDec[5];               // seuil d'action, f_max, gamma, stop_max, tp_max
    __shared__ float sYo[WP][4];            // probabilites a l'ouverture de la position en cours
    __shared__ float sR[2][WP];             // r d'une fermeture au repos, d'une fermeture decidee
    __shared__ __align__(16) int sDrap[3][WP];  // fermeture au repos, fermeture decidee, ouverture
    __shared__ int sFerme[WP];              // fermeture au repos sur la barre : pas d'ouverture ensuite
    __shared__ i64 sNum[8][WP], sDen[8][WP];  // rapports des entrees d'etat, poses par les meneurs
    __shared__ int sTenue[WP];
    __shared__ float sAct[WP][8];           // probabilites des trois actions, puis sigmoides des quatre sorties
    __shared__ float sO[WP][8];             // sorties brutes du reseau, pour les traces
    __shared__ int sFen[3][WP];             // debut, prechauffage et fin de chaque fenetre
    __shared__ i64 sCout[2][WP];            // frais et glissement, en millioniemes
    __shared__ Couloirs S;

    const int bot = blockIdx.x;
    const int t = threadIdx.x;
    const int lane = t & 31, warp = t >> 5;
    const Marche& m = sM;
    const Reglages& R = sReg;

    if (t == 0) {
        sM.indices = pointeur<const i64>(M, M_INDICES);
        sM.local = pointeur<const i64>(M, M_LOCAL);
        sM.cloture = pointeur<const float>(M, M_CLOTURE);
        sM.volume = pointeur<const float>(M, M_VOLUME);
        sM.moyennes = pointeur<const float>(M, M_MOYENNES);
        sM.ecarts_types = pointeur<const float>(M, M_ECARTS_TYPES);
        sM.volumes_moyens = pointeur<const float>(M, M_VOLUMES_MOYENS);
        sM.atr = pointeur<const float>(M, M_ATR);
        sM.max_haut = pointeur<const float>(M, M_MAX_HAUT);
        sM.min_bas = pointeur<const float>(M, M_MIN_BAS);
        sM.niveau_de = pointeur<const i64>(M, M_NIVEAU_DE);
        sM.ouverture_c = pointeur<const float>(M, M_OUVERTURE_C);
        sM.haut_c = pointeur<const float>(M, M_HAUT_C);
        sM.bas_c = pointeur<const float>(M, M_BAS_C);
        sM.volatilites = pointeur<const float>(M, M_VOLATILITES);
        sM.ema = pointeur<const float>(M, M_EMA);
        sM.somme_typique = pointeur<const double>(M, M_SOMME_TYPIQUE);
        sM.somme_pression = pointeur<const double>(M, M_SOMME_PRESSION);
        sM.segment = pointeur<const i64>(M, M_SEGMENT);
        sM.heure = pointeur<const unsigned char>(M, M_HEURE);
        sM.jour = pointeur<const unsigned char>(M, M_JOUR);
        for (int q = 0; q < NTABLES; ++q) sM.tables[q] = pointeur<const float>(M, M_TABLES + q);
        sM.n1 = (int)M[M_N1];
        sM.ncomb = (int)M[M_NCOMB];
        sM.ouv = pointeur<const i64>(M, M_OUV);
        sM.haut = pointeur<const i64>(M, M_HAUT);
        sM.bas = pointeur<const i64>(M, M_BAS);
        sM.clo = pointeur<const i64>(M, M_CLO);
        sM.temps = pointeur<const float4>(M, M_TEMPS);
        sM.minuit = pointeur<const unsigned char>(M, M_MINUIT);
        sReg.Lt = (int)P[P_LT];
        sReg.periode_atr = (int)pointeur<const i64>(P, P_PERIODE_ATR)[bot];
        sReg.B = (int)P[P_B];
    }

    // Colonne de poids du neurone t et ses poids de sortie, en registres ; le reste du bot, en memoire partagee.
    float wcol[EH];
    {
        const float* poids = pointeur<const float>(P, P_W) + (i64)bot * EH * H + t;
        #pragma unroll
        for (int e = 0; e < EH; ++e) wcol[e] = poids[(i64)e * H];
    }
    const float biais_cache = pointeur<const float>(P, P_B_CACHE)[(i64)bot * H + t];
    float wo[4];
    {
        const float* poids = pointeur<const float>(P, P_W_SORTIE) + ((i64)bot * H + t) * 4;
        #pragma unroll
        for (int o = 0; o < 4; ++o) wo[o] = poids[o];
    }
    if (t < 3) sBiais[t] = pointeur<const float>(P, P_B_ACTION)[(i64)bot * 3 + t];
    if (t < 4) sBiais[3 + t] = pointeur<const float>(P, P_B_SORTIE)[(i64)bot * 4 + t];
    if (t < 5) sDec[t] = pointeur<const float>(P, P_DECISION)[(i64)bot * 5 + t];
    for (int q = t; q < NG; q += H) sG[q] = pointeur<const float>(P, P_GENES)[(i64)bot * NG + q];

    // Fenetres et etat des couloirs.
    {
        const int L = (int)P[P_L];
        const i64 premier = (i64)bot * W;  // premier couloir du bot
        const i64* fen = pointeur<const i64>(P, P_FENETRES);
        const i64* e64 = pointeur<const i64>(P, P_ETAT64);
        const double* ef = pointeur<const double>(P, P_ETATF);
        const i64* g_sorties = pointeur<const i64>(P, P_SORTIES);
        const float* g_derniers = pointeur<const float>(P, P_DERNIERS);
        const i64* g_anneau = pointeur<const i64>(P, P_ANNEAU);
        const i64* g_ruine = pointeur<const i64>(P, P_RUINE);
        const float* g_yo = pointeur<const float>(P, P_YO);
        const float* g_h = pointeur<const float>(P, P_H);
        const float* g_ho = pointeur<const float>(P, P_HO);
        const float* g_wa = pointeur<const float>(P, P_WA);
        for (int q = t; q < 3 * W; q += H) sFen[q / W][q % W] = (int)fen[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < 2 * W; q += H) sCout[q / W][q % W] = fen[(3 + q / W) * (i64)L + premier + q % W];
        for (int q = t; q < NETAT * W; q += H) S.e[q / W][q % W] = e64[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < 7 * W; q += H) S.f[q / W][q % W] = ef[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < 5 * W; q += H) S.sorties[q / W][q % W] = g_sorties[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < 5 * W; q += H) S.derniers[q / W][q % W] = g_derniers[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < 24 * W; q += H) S.anneau[q / W][q % W] = g_anneau[(q / W) * (i64)L + premier + q % W];
        for (int q = t; q < W; q += H) S.ruine[q] = (int)g_ruine[premier + q];
        for (int q = t; q < 3 * W; q += H) sYo[q / 3][q % 3] = g_yo[(premier + q / 3) * 3 + q % 3];
        for (int q = t; q < 3 * WP; q += H) sDrap[q / WP][q % WP] = 0;
        // Etat du neurone t dans chaque fenetre : dernier etat cache, etat cache a l'ouverture, poids d'action.
        for (int w = 0; w < W; ++w) {
            const i64 x = (premier + w) * H + t;
            (&sH[0][t].x)[w] = g_h[x];
            sHo[w][t] = g_ho[x];
            for (int j = 0; j < 3; ++j) sWa[w][j][t] = g_wa[x * 3 + j];
        }
    }
    __syncthreads();
    int finmax = 0;
    for (int w = 0; w < W; ++w) finmax = sFen[2][w] > finmax ? sFen[2][w] : finmax;

    const int limite = k0 + pas < finmax ? k0 + pas : finmax;
    int lu = 0;  // tampon de l'etat cache de la barre precedente
    for (int kb = k0; kb < limite; kb += AVANCE) {
        const int nb = limite - kb < AVANCE ? limite - kb : AVANCE;
        __syncthreads();  // les meneurs ont fini la barre precedente

        // Lecture d'avance : barres et signaux des modules, un couple (fenetre, barre) par fil. Chaque signal
        // entre aussitot dans les canaux, par la projection du bot : produit puis somme, arrondis a part, dans
        // l'ordre des modules. En trace complete, les signaux bruts sont ecrits tels quels.
        for (int q = t; q < W * AVANCE; q += H) {
            const int w = q / AVANCE, b = q - w * AVANCE;
            if (b >= nb) continue;
            int i = sFen[0][w] + kb + b;
            if (i > m.n1 - 1) i = m.n1 - 1;
            sOuv[b][w] = m.ouv[i];
            sHaut[b][w] = m.haut[i];
            sBas[b][w] = m.bas[i];
            sClo[b][w] = m.clo[i];
            sTemps[b][w] = m.temps[i];
            sMinuit[b][w] = m.minuit[i];
            sAtr[b][w] = atr_en(m, R.periode_atr, i);
            const float* projection = relu<const float>(P, P_PROJ) + (i64)bot * NMOD * CANAUX;
            float* entrees = nullptr;
            if (COMPLET) {
                const int couloir = bot * W + w;
                if (couloir < R.Lt) entrees = relu<float>(P, P_T_ENTREES) + ((i64)(kb + b) * R.Lt + couloir) * NTRACE;
            }
            float canal[CANAUX];
            #pragma unroll
            for (int c = 0; c < CANAUX; ++c) canal[c] = 0.f;
            #pragma unroll
            for (int module = 0; module < NMOD; ++module) {
                float v = signal_module(m, module, sG + MODULE_DEBUT[module], i, R.periode_atr);
                if (!isfinite(v)) v = 0.f;
                if (COMPLET && entrees) entrees[module] = v;
                #pragma unroll
                for (int c = 0; c < CANAUX; ++c)
                    canal[c] = __fadd_rn(canal[c], __fmul_rn(projection[module * CANAUX + c], v));
            }
            #pragma unroll
            for (int c = 0; c < CANAUX; ++c) (&sCh[b][c].x)[w] = canal[c];
        }
        __syncthreads();

        for (int b = 0; b < nb; ++b) {
            const int k = kb + b;

            // Phase 1 (meneurs) : ordres au repos, puis entrees d'etat.
            if (t < W) {
                const int w = t;
                const Champs c{&S.e[0][w]};
                const int fin = sFen[2][w];
                const bool actif = k < fin;
                const bool note = actif && k >= sFen[1][w];
                const i64 C = sClo[b][w];
                i64 qte = c[QTE];
                const i64 stop_pose = c[STOP], cible_posee = c[CIBLE];
                const bool en_position = qte > 0 && note;
                const bool stop = en_position && sBas[b][w] <= stop_pose;
                const bool cible = en_position && !stop && sHaut[b][w] >= cible_posee;
                const bool ferme_a = stop || cible;
                float r_a = 0.f;
                i64 prix_repos = 0;
                if (ferme_a) {
                    const i64 ouverture = sOuv[b][w];
                    const i64 reference = stop ? (stop_pose < ouverture ? stop_pose : ouverture) : cible_posee;
                    prix_repos = reference * (MILLION - sCout[1][w]) / MILLION;
                    r_a = fermer(S, w, prix_repos, stop ? R_STOP : R_CIBLE, sCout[0][w]);
                    qte = 0;
                }
                sFerme[w] = ferme_a ? 1 : 0;
                sDrap[0][w] = (ferme_a && ADAPTATION) ? 1 : 0;
                sR[0][w] = r_a;
                const int couloir = bot * W + w;
                if (COMPLET && couloir < R.Lt) {
                    const i64 x = (i64)k * R.Lt + couloir;
                    relu<i64>(P, P_T_PRIX_REPOS)[x] = prix_repos;
                    relu<i64>(P, P_T_RAISON_REPOS)[x] = stop ? R_STOP : (cible ? R_CIBLE : -1);
                }
                const bool tenue = qte > 0;
                i64 duree = c[DUREE];
                if (tenue && note) c[DUREE] = ++duree;
                const i64 valeur = qte * C * MILLION;
                const i64 capital = c[CASH] + valeur;
                i64 jour = c[JOUR_REF];
                if (sMinuit[b][w] && actif) c[JOUR_REF] = jour = capital;
                const i64 frais_24h = c[FRAIS_CUM] - S.anneau[k % 24][w];
                const i64 pic = c[PIC] > capital ? c[PIC] : capital;
                const i64 entree = c[PRIX_ENTREE] > 1 ? c[PRIX_ENTREE] : 1;
                // Les huit rapports des entrees d'etat, que le warp calcule ensuite, un par fil.
                sNum[0][w] = valeur;             sDen[0][w] = capital;
                sNum[1][w] = C - entree;         sDen[1][w] = entree;
                sNum[2][w] = duree;              sDen[2][w] = 1;
                sNum[3][w] = C - stop_pose;      sDen[3][w] = 1;
                sNum[4][w] = cible_posee - C;    sDen[4][w] = 1;
                sNum[5][w] = capital - jour;     sDen[5][w] = jour;
                sNum[6][w] = frais_24h;          sDen[6][w] = capital;
                sNum[7][w] = pic - capital;      sDen[7][w] = pic;
                sTenue[w] = tenue ? 1 : 0;
                float* x = &sX[0].x + w;  // entree d'etat r de la fenetre w : x[4 * r]
                x[4 * 0] = tenue ? 1.f : 0.f;
                for (int q = 0; q < 5; ++q) x[4 * (8 + q)] = S.derniers[q][w];
                const float4 temps = sTemps[b][w];
                x[4 * 14] = temps.x;
                x[4 * 15] = temps.y;
                x[4 * 16] = temps.z;
                x[4 * 17] = temps.w;
            }
            if (warp == 0) {
                // Rapports en simple precision, sur des differences entieres exactes : le fil (d, w) calcule le
                // rapport d de la fenetre w. Les entrees 4 et 5 sont des distances en ATR. La duree se divise
                // comme PyTorch divise par un scalaire : produit par l'inverse, calcule en double puis arrondi.
                __syncwarp();
                const int w = lane & (WP - 1), d = lane >> 2;
                if (w < W) {
                    const float a = (float)sNum[d][w];
                    const float quotient = a / (float)sDen[d][w];
                    const float atr = sAtr[b][w];
                    const float inverse = atr > 0.f ? 1.f / atr : 0.f;
                    float v = (d == 3 || d == 4) ? a * PAS_F * inverse : (d == 2 ? a * (float)(1.0 / DUREE_BARRES) : quotient);
                    if (d >= 1 && d <= 4 && !sTenue[w]) v = 0.f;
                    (&sX[d < 7 ? d + 1 : 13].x)[w] = v;
                }
            }
            __syncthreads();

            // Phase 2 (tous) : adaptations en attente, puis reseau recurrent. Une ouverture ou une fermeture
            // decidee a la barre precedente se traite avant la fermeture au repos de celle-ci : c'est l'ordre
            // des evenements. L'etat cache de la barre precedente est dans sH[lu].
            {
                const int4 d0 = *reinterpret_cast<const int4*>(sDrap[0]);
                const int4 d1 = *reinterpret_cast<const int4*>(sDrap[1]);
                const int4 d2 = *reinterpret_cast<const int4*>(sDrap[2]);
                if (d0.x | d0.y | d0.z | d0.w | d1.x | d1.y | d1.z | d1.w | d2.x | d2.y | d2.z | d2.w) {
                    for (int w = 0; w < W; ++w) {
                        if (sDrap[2][w]) sHo[w][t] = (&sH[lu][t].x)[w];
                        if (sDrap[1][w]) adapter_fenetre(sWa, sHo, sYo, P, R.B, bot, t, w, sR[1][w]);
                        if (sDrap[0][w]) adapter_fenetre(sWa, sHo, sYo, P, R.B, bot, t, w, sR[0][w]);
                    }
                }
            }
            float hn[W];
            {
                float acc[W];
                #pragma unroll
                for (int w = 0; w < W; ++w) acc[w] = biais_cache;
                #pragma unroll
                for (int e = 0; e < CANAUX; ++e) {
                    const float4 v = sCh[b][e];
                    #pragma unroll
                    for (int w = 0; w < W; ++w) acc[w] = fmaf(wcol[e], composante(v, w), acc[w]);
                }
                #pragma unroll
                for (int e = CANAUX; e < E; ++e) {
                    const float4 v = sX[e - CANAUX];
                    #pragma unroll
                    for (int w = 0; w < W; ++w) acc[w] = fmaf(wcol[e], composante(v, w), acc[w]);
                }
                #pragma unroll
                for (int e = E; e < EH; ++e) {
                    const float4 v = sH[lu][e - E];
                    #pragma unroll
                    for (int w = 0; w < W; ++w) acc[w] = fmaf(wcol[e], composante(v, w), acc[w]);
                }
                #pragma unroll
                for (int w = 0; w < W; ++w) hn[w] = tanhf(acc[w]);
            }
            // Phase 3 (tous) : nouvel etat cache, dans l'autre tampon, sans attendre que les autres fils aient lu
            // celui-ci ; puis sommes des sept sorties de chaque fenetre sur le warp. Les valeurs d'indice
            // w * NS + j se replient de moitie en moitie : a la fin, le fil de rang r du warp tient la somme de la
            // valeur d'indice r.
            {
                float4 v = make_float4(0.f, 0.f, 0.f, 0.f);
                #pragma unroll
                for (int w = 0; w < W; ++w) (&v.x)[w] = hn[w];
                sH[1 - lu][t] = v;
                lu = 1 - lu;
            }
            {
                float s[16];
                const bool haut = (lane & 16) != 0;
                #pragma unroll
                for (int q = 0; q < 16; ++q) {
                    float bas_ = 0.f, haut_ = 0.f;
                    #pragma unroll
                    for (int moitie = 0; moitie < 2; ++moitie) {
                        const int r = q + 16 * moitie, w = r / NS, j = r - w * NS;
                        float valeur = 0.f;
                        if (w < W) valeur = hn[w] * (j < 3 ? sWa[w][j < 3 ? j : 0][t] : wo[j < 3 ? 0 : j - 3]);
                        if (moitie == 0) bas_ = valeur; else haut_ = valeur;
                    }
                    const float envoi = haut ? bas_ : haut_;
                    s[q] = (haut ? haut_ : bas_) + __shfl_xor_sync(0xffffffffu, envoi, 16);
                }
                replier<8>(s, lane);
                replier<4>(s, lane);
                replier<2>(s, lane);
                replier<1>(s, lane);
                sPart[warp][lane] = s[0];
            }
            __syncthreads();

            // Phase 4 : activations des sorties sur le warp 0, le fil (w, j) pour la sortie j de la fenetre w ;
            // puis decision a la cloture et comptes (meneurs). Les autres fils passent a la barre suivante, ou ils
            // attendent les meneurs : rien de ce qu'ecrit cette phase ne leur sert avant.
            if (warp == 0) {
                const int w = lane >> 3, j = lane & 7;
                float o = 0.f;
                if (w < W && j < NS) {
                    o = sPart[0][w * NS + j];
                    #pragma unroll
                    for (int v = 1; v < NW; ++v) o += sPart[v][w * NS + j];
                    o += sBiais[j];
                }
                // Softmax des trois scores d'action de la fenetre, dans le meme ordre d'operations pour chaque fil.
                const float o0 = __shfl_sync(0xffffffffu, o, lane & ~7), o1 = __shfl_sync(0xffffffffu, o, (lane & ~7) + 1),
                            o2 = __shfl_sync(0xffffffffu, o, (lane & ~7) + 2);
                const float plus = fmaxf(o0, fmaxf(o1, o2));
                const float e0 = expf(o0 - plus), e1 = expf(o1 - plus), e2 = expf(o2 - plus);
                const float somme = e0 + e1 + e2;
                if (w < W && j < NS) {
                    sAct[w][j] = j < 3 ? (j == 0 ? e0 : (j == 1 ? e1 : e2)) / somme : sigmoide(o);
                    sO[w][j] = o;
                }
                __syncwarp();
            }
            if (t < W) {
                const int w = t;
                const Champs c{&S.e[0][w]};
                const int fin = sFen[2][w];
                const bool note = k < fin && k >= sFen[1][w];
                const bool derniere = k == fin - 1;
                const i64 frais_ppm = sCout[0][w], gliss = sCout[1][w];
                const i64 C = sClo[b][w];
                const float p_achat = sAct[w][0], p_vente = sAct[w][1], p_garde = sAct[w][2];
                // Conserver l'emporte en cas d'egalite, puis acheter.
                int choix = 0;
                float p = p_garde;
                if (p_achat > p) { choix = 1; p = p_achat; }
                if (p_vente > p) { choix = 2; p = p_vente; }
                const float seuil = sDec[0];
                const bool agit = p >= seuil;
                const bool achat = agit && choix == 1;
                const bool vente = agit && choix == 2;
                const float atr = sAtr[b][w];
                const bool atr_ok = atr > 0.f;
                // Sorties decidees : duree, vente, fin de fenetre, remplies au cours de cloture.
                i64 qte = c[QTE];
                const bool garde = qte > 0 && note;
                const bool s_duree = garde && c[DUREE] >= c[DUREE_MAX];
                const bool s_vente = garde && !s_duree && vente;
                const bool s_fin = garde && !s_duree && !s_vente && derniere;
                const bool sortie = s_duree || s_vente || s_fin;
                const i64 prix_vente = C * (MILLION - gliss) / MILLION;
                const int raison = s_duree ? R_DUREE : (s_vente ? R_VENTE : R_FIN);
                float r_f = 0.f;
                if (sortie) {
                    r_f = fermer(S, w, prix_vente, raison, frais_ppm);
                    qte = 0;
                }
                sDrap[1][w] = (sortie && !derniere && ADAPTATION) ? 1 : 0;
                sR[1][w] = r_f;
                // Protections fixees par le reseau, jamais sous le plancher de 5 %. Ouverture : jamais sur une barre
                // ou une position a ete fermee, ni sur la derniere barre.
                const bool maj = qte > 0 && note && atr_ok;
                const bool candidat = note && qte == 0 && !sFerme[w] && !sortie && !derniere && achat && atr_ok;
                i64 stop_voulu = 0, cible_voulue = 0;
                if (maj || candidat) {
                    const double distance = (double)atr * INV_PAS;
                    const float k_stop = 0.5f + (sDec[3] - 0.5f) * sAct[w][4];
                    const float k_cible = 0.5f + (sDec[4] - 0.5f) * sAct[w][5];
                    stop_voulu = (i64)ceil((double)C - (double)k_stop * distance);
                    cible_voulue = (i64)ceil((double)C + (double)k_cible * distance);
                }
                if (maj) {
                    const i64 plancher = (c[PRIX_ENTREE] * (100 - PLANCHER) + 99) / 100;
                    c[STOP] = stop_voulu > plancher ? stop_voulu : plancher;
                    c[CIBLE] = cible_voulue;
                }
                bool ouvre = false;
                i64 q = 0, prix_achat = 0;
                if (candidat) {
                    prix_achat = (C * (MILLION + gliss) + MILLION - 1) / MILLION;
                    const float rapport = positif((p - seuil) / (1.f - seuil));
                    const float fraction = sDec[1] * sAct[w][3] * powf(rapport, sDec[2]);
                    const i64 cash = c[CASH];
                    const i64 voulue = (i64)floor((double)fraction * (double)cash / ((double)prix_achat * (double)MILLION));
                    const i64 possible = cash / (prix_achat * (MILLION + frais_ppm));
                    q = voulue < possible ? voulue : possible;
                    if (q < 0) q = 0;
                    const i64 notionnel = prix_achat * q * MILLION;
                    ouvre = q > 0 && notionnel >= NOTIONNEL_MIN;
                    if (ouvre) {
                        const i64 frais = prix_achat * q * frais_ppm;
                        const i64 plancher = (prix_achat * (100 - PLANCHER) + 99) / 100;
                        const i64 stop_ouv = stop_voulu > plancher ? stop_voulu : plancher;
                        c[CAPITAL_OUV] = cash;
                        c[CASH] = cash - notionnel - frais;
                        c[QTE] = q;
                        c[PRIX_ENTREE] = prix_achat;
                        c[FRAIS_ENTREE] = frais;
                        c[DUREE] = 0;
                        c[DUREE_MAX] = (i64)rintf(1.f + (float)(DUREE_BARRES - 1) * sAct[w][6]);
                        c[STOP] = stop_ouv;
                        c[CIBLE] = cible_voulue;
                        const i64 risque = q * (prix_achat - stop_ouv) * MILLION;
                        const i64 minimum = notionnel / 1000;
                        c[RISQUE0] = risque > minimum ? risque : minimum;
                        c[FRAIS_TOTAL] += frais;
                        c[FRAIS_CUM] += frais;
                        c[ROTATION] += notionnel;
                        sYo[w][0] = p_achat;
                        sYo[w][1] = p_vente;
                        sYo[w][2] = p_garde;
                        qte = q;
                    }
                }
                sDrap[2][w] = ouvre ? 1 : 0;
                // Comptes de fin de barre. Le drawdown garde la barre qui le realise : capital et pic, compares
                // exactement.
                const i64 fin_barre = c[CASH] + qte * C * MILLION;
                if (note) {
                    const i64 pic = c[PIC];
                    if (fin_barre > pic) {
                        c[PIC] = fin_barre;
                    } else if (fin_barre < pic && (c[DD_PIC] == 0 || plus_petit(fin_barre, pic, c[DD_FIN], c[DD_PIC]))) {
                        c[DD_FIN] = fin_barre;
                        c[DD_PIC] = pic;
                    }
                    if (fin_barre < SEUIL_RUINE) S.ruine[w] = 1;
                }
                if (TRACE && note) {  // moments des rendements, tenus avec une trace
                    const double r = (double)fin_barre / (double)c[CAPITAL_PREC] - 1.0;
                    const double carre = r * r;
                    S.f[M1][w] += r;
                    S.f[M2][w] += carre;
                    S.f[M3][w] += carre * r;
                    S.f[M4][w] += carre * carre;
                    c[CAPITAL_PREC] = fin_barre;
                }
                S.anneau[k % 24][w] = c[FRAIS_CUM];
                const int couloir = bot * W + w;
                if (TRACE && couloir < R.Lt) {
                    const i64 x = (i64)k * R.Lt + couloir;
                    float* t_fraction = relu<float>(P, P_T_FRACTION);
                    if (t_fraction) {
                        t_fraction[x] = note ? (float)((double)(qte * C * MILLION) / (double)fin_barre) : 0.f;
                    }
                    if (COMPLET) {
                        const int code = ouvre ? D_OUVERTURE : (sortie ? D_FERMETURE : (maj ? D_PROTECTION : D_RIEN));
                        relu<i64>(P, P_T_CAPITAL)[x] = fin_barre;
                        relu<i64>(P, P_T_CASH)[x] = c[CASH];
                        relu<i64>(P, P_T_DECISION)[x] = code;
                        relu<i64>(P, P_T_RAISON)[x] = sortie ? raison : -1;
                        relu<i64>(P, P_T_QUANTITE)[x] = ouvre ? q : 0;
                        relu<i64>(P, P_T_QUANTITE_TENUE)[x] = qte;
                        relu<i64>(P, P_T_PRIX)[x] = ouvre ? prix_achat : (sortie ? prix_vente : 0);
                        relu<i64>(P, P_T_STOP)[x] = c[STOP];
                        relu<i64>(P, P_T_CIBLE)[x] = c[CIBLE];
                        float* probas = relu<float>(P, P_T_PROBAS) + x * 3;
                        probas[0] = p_achat;
                        probas[1] = p_vente;
                        probas[2] = p_garde;
                        float* sorties_reseau = relu<float>(P, P_T_SORTIES) + x * 4;
                        #pragma unroll
                        for (int j = 0; j < 4; ++j) sorties_reseau[j] = sO[w][3 + j];
                        // Les entrees d'etat de cette barre, apres ses signaux, ecrits a la lecture d'avance.
                        float* entrees = relu<float>(P, P_T_ENTREES) + x * NTRACE + NMOD;
                        for (int e = 0; e < ETATS; ++e) entrees[e] = (&sX[e].x)[w];
                    }
                }
            }
        }
    }
    __syncthreads();

    // Adaptations en attente de la derniere barre de l'appel, puis retour de l'etat en memoire globale.
    for (int w = 0; w < W; ++w) {
        if (sDrap[2][w]) sHo[w][t] = (&sH[lu][t].x)[w];
        if (sDrap[1][w]) adapter_fenetre(sWa, sHo, sYo, P, R.B, bot, t, w, sR[1][w]);
    }
    {
        const int L = (int)((volatile const i64*)P)[P_L];
        const i64 premier = (i64)bot * W;
        float* g_h = relu<float>(P, P_H);
        float* g_ho = relu<float>(P, P_HO);
        float* g_wa = relu<float>(P, P_WA);
        for (int w = 0; w < W; ++w) {
            const i64 x = (premier + w) * H + t;
            g_h[x] = (&sH[lu][t].x)[w];
            g_ho[x] = sHo[w][t];
            for (int j = 0; j < 3; ++j) g_wa[x * 3 + j] = sWa[w][j][t];
        }
        i64* e64 = relu<i64>(P, P_ETAT64);
        double* ef = relu<double>(P, P_ETATF);
        i64* g_sorties = relu<i64>(P, P_SORTIES);
        float* g_derniers = relu<float>(P, P_DERNIERS);
        i64* g_anneau = relu<i64>(P, P_ANNEAU);
        i64* g_ruine = relu<i64>(P, P_RUINE);
        float* g_yo = relu<float>(P, P_YO);
        for (int q = t; q < NETAT * W; q += H) e64[(q / W) * (i64)L + premier + q % W] = S.e[q / W][q % W];
        for (int q = t; q < 7 * W; q += H) {
            const int champ = q / W, w = q % W;
            ef[champ * (i64)L + premier + w] = champ == DD ? drawdown(S.e[DD_FIN][w], S.e[DD_PIC][w]) : S.f[champ][w];
        }
        for (int q = t; q < 5 * W; q += H) g_sorties[(q / W) * (i64)L + premier + q % W] = S.sorties[q / W][q % W];
        for (int q = t; q < 5 * W; q += H) g_derniers[(q / W) * (i64)L + premier + q % W] = S.derniers[q / W][q % W];
        for (int q = t; q < 24 * W; q += H) g_anneau[(q / W) * (i64)L + premier + q % W] = S.anneau[q / W][q % W];
        for (int q = t; q < W; q += H) g_ruine[premier + q] = S.ruine[q];
        for (int q = t; q < 3 * W; q += H) g_yo[(premier + q / 3) * 3 + q % 3] = sYo[q / 3][q % 3];
    }
}
