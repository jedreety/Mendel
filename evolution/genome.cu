// Noyaux CUDA des genomes (ARCHITECTURE.md, section 21.6) : generation 0 et mutation, compiles par NVRTC.
//
// evolution/genome.py place avant ce texte TAILLE (genes d'un genome), ND (genes discrets) et NPAIRES (paires
// de periodes ordonnees). Un bloc par genome. Le calcul est celui des operations PyTorch de genome.py et de
// philox.py, operation par operation, arrondi par arrondi : aucune contraction en FMA, et un scalaire se
// combine a un tenseur comme dans PyTorch, arrondi en simple, un diviseur remplace par son inverse calcule en
// double puis arrondi en simple. Les genomes sont identiques au bit pres a ceux de la version PyTorch.

typedef long long i64;
typedef unsigned int u32;

// Codes des genes, comme genome.py.
#define REEL 0
#define ENTIER 1
#define CATEGORIEL 2
#define SIGMA 3
// Role d'un gene a la generation 0.
#define TIRE 0              // uniforme dans ses bornes
#define POIDS 1             // loi normale reduite puis bornee
#define DEMI 2              // biais : 0,5
#define AMPLITUDE 3         // amplitude de mutation initiale des modules, de la decision, de l'adaptation
#define AMPLITUDE_RESEAU 4  // amplitude de mutation initiale du reseau
// Flux d'un genome, deuxieme mot du compteur, comme philox.py.
#define NORMALES 0
#define UNIFORMES 1
#define UNIFORMES_BIS 2
#define NORMALES_SIGMA 3
#define AMPLEURS 4
#define FORCE 5

#define DEUX_PI 6.28318548202514648f  // 2 pi arrondi en simple, comme le scalaire de philox.normales

// Philox4x32-10 : quatre mots pour la cle (k0, k1) et le compteur (c0, c1, c2, c3), comme philox.bloc.
__device__ __forceinline__ uint4 philox(u32 k0, u32 k1, u32 c0, u32 c1, u32 c2, u32 c3) {
    #pragma unroll
    for (int tour = 0; tour < 10; ++tour) {
        if (tour) {
            k0 += 0x9E3779B9u;
            k1 += 0xBB67AE85u;
        }
        const u32 hi0 = __umulhi(0xD2511F53u, c0), lo0 = 0xD2511F53u * c0;
        const u32 hi1 = __umulhi(0xCD9E8D57u, c2), lo1 = 0xCD9E8D57u * c2;
        const u32 n0 = hi1 ^ c1 ^ k0, n2 = hi0 ^ c3 ^ k1;
        c0 = n0;
        c1 = lo1;
        c2 = n2;
        c3 = lo0;
    }
    return make_uint4(c0, c1, c2, c3);
}

__device__ __forceinline__ u32 mot(const uint4& m, int j) { return j == 0 ? m.x : (j == 1 ? m.y : (j == 2 ? m.z : m.w)); }

// Reel sur [0, 1) : les 24 bits de poids fort du mot, exact en simple.
__device__ __forceinline__ float uniforme(u32 m) { return __fmul_rn((float)(m >> 8), 5.9604644775390625e-08f); }

// Deux normales de Box-Muller a partir de deux mots, comme philox.normales.
__device__ __forceinline__ float2 normales(u32 a, u32 b) {
    const float u1 = __fmul_rn((float)((a >> 8) + 1), 5.9604644775390625e-08f);
    const float u2 = __fmul_rn((float)(b >> 8), 5.9604644775390625e-08f);
    const float rayon = __fsqrt_rn(__fmul_rn(-2.0f, logf(u1)));
    const float angle = __fmul_rn(DEUX_PI, u2);
    return make_float2(__fmul_rn(rayon, cosf(angle)), __fmul_rn(rayon, sinf(angle)));
}

// Les quatre normales du bloc c d'un flux : normales 4c a 4c + 3.
__device__ __forceinline__ float4 quatre_normales(u32 k0, u32 k1, u32 c, u32 flux) {
    const uint4 m = philox(k0, k1, c, flux, 0, 0);
    const float2 a = normales(m.x, m.y), b = normales(m.z, m.w);
    return make_float4(a.x, a.y, b.x, b.y);
}

__device__ __forceinline__ float composante(const float4& v, int j) {
    return j == 0 ? v.x : (j == 1 ? v.y : (j == 2 ? v.z : v.w));
}

__device__ __forceinline__ float borner(float v) { return fminf(fmaxf(v, 0.f), 1.f); }

// Si une periode courte depasse la longue, les deux valeurs naturelles sont echangees (genome._ordonner).
// Une paire : indices des deux genes, puis pour chacun entier (1) ou reel (0), et les constantes de
// naturel = a + u b et de normaliser = ((v - bas) + demi) * inverse, arrondies en simple comme PyTorch.
__device__ void ordonner(float* x, const float* paires) {
    for (int p = 0; p < NPAIRES; ++p) {
        const float* q = paires + 12 * p;
        const int ia = (int)q[0], ib = (int)q[1];
        const float na = __fadd_rn(q[3], __fmul_rn(x[ia], q[4]));
        const float nb = __fadd_rn(q[8], __fmul_rn(x[ib], q[9]));
        if (na > nb) {
            const float ua = q[2] != 0.f ? __fadd_rn(__fsub_rn(nb, q[5]), 0.5f) : __fsub_rn(nb, q[5]);
            const float ub = q[7] != 0.f ? __fadd_rn(__fsub_rn(na, q[10]), 0.5f) : __fsub_rn(na, q[10]);
            x[ia] = borner(__fmul_rn(ua, q[6]));
            x[ib] = borner(__fmul_rn(ub, q[11]));
        }
    }
}

// Bots tires au hasard (Disposition.generation0) : cles (n, 2), sortie (n, TAILLE).
extern "C" __global__ void generation0(const i64* __restrict__ cles, const unsigned char* __restrict__ code,
                                       const unsigned char* __restrict__ role, const float* __restrict__ categories,
                                       const float* __restrict__ inverse, const float* __restrict__ paires,
                                       double sigma_reseau, double sigma_autres, float* __restrict__ sortie) {
    const u32 k0 = (u32)cles[2 * blockIdx.x], k1 = (u32)cles[2 * blockIdx.x + 1];
    float* x = sortie + (i64)blockIdx.x * TAILLE;
    for (int c = threadIdx.x; c < (TAILLE + 3) / 4; c += blockDim.x) {
        const uint4 mu = philox(k0, k1, c, UNIFORMES, 0, 0);
        const float4 z = quatre_normales(k0, k1, c, NORMALES);
        for (int j = 0; j < 4; ++j) {
            const int g = 4 * c + j;
            if (g >= TAILLE) break;
            const float u = uniforme(mot(mu, j));
            float v;
            switch (role[g]) {
                case POIDS: v = borner(__fadd_rn(0.5f, __fmul_rn(composante(z, j), inverse[g]))); break;
                case DEMI: v = 0.5f; break;
                case AMPLITUDE: v = (float)sigma_autres; break;
                case AMPLITUDE_RESEAU: v = (float)sigma_reseau; break;
                default:
                    v = code[g] == CATEGORIEL ? floorf(__fmul_rn(u, categories[g])) : u;
            }
            x[g] = v;
        }
    }
    __syncthreads();
    if (threadIdx.x == 0) ordonner(x, paires);
}

// Enfants des parents choisis (Disposition.muter) : parents (p, TAILLE), choix (n), cles (n, 2), tau (4),
// bornes (2, 4) des amplitudes, discrets (ND), sortie (n, TAILLE). Les amplitudes mutent d'abord, dans leurs
// bornes. Puis l'enfant tire sa force, et chaque gene
// son ampleur, log-uniformes : exp(debut + u x etendue). x' = x + sigma x force x ampleur x N(0, 1), borne ou pris
// modulo 1. Un gene categoriel est retire au hasard avec la probabilite proba_categoriel.
extern "C" __global__ void muter(const float* __restrict__ parents, const i64* __restrict__ choix,
                                 const i64* __restrict__ cles, const unsigned char* __restrict__ code,
                                 const unsigned char* __restrict__ groupe, const unsigned char* __restrict__ circulaire,
                                 const float* __restrict__ categories, const int* __restrict__ discrets,
                                 const float* __restrict__ tau, const float* __restrict__ paires,
                                 const float* __restrict__ bornes, double proba_categoriel, double debut_force,
                                 double etendue_force,
                                 double debut_ampleur, double etendue_ampleur, float* __restrict__ sortie) {
    __shared__ float sigma[4];
    __shared__ float force[4];  // amplitude de chaque groupe multipliee par la force de l'enfant
    const u32 k0 = (u32)cles[2 * blockIdx.x], k1 = (u32)cles[2 * blockIdx.x + 1];
    const float* x = parents + choix[blockIdx.x] * TAILLE;
    float* y = sortie + (i64)blockIdx.x * TAILLE;
    if (threadIdx.x == 0) {
        const float4 z = quatre_normales(k0, k1, 0, NORMALES_SIGMA);
        const float u = uniforme(philox(k0, k1, 0, FORCE, 0, 0).x);
        const float f = expf(__fadd_rn(__fmul_rn(u, (float)etendue_force), (float)debut_force));
        for (int g = 0; g < 4; ++g) {
            const float s = __fmul_rn(x[g], expf(__fmul_rn(tau[g], composante(z, g))));
            sigma[g] = fminf(fmaxf(s, bornes[g]), bornes[4 + g]);
            force[g] = __fmul_rn(sigma[g], f);
        }
    }
    __syncthreads();
    for (int c = threadIdx.x; c < (TAILLE + 3) / 4; c += blockDim.x) {
        const float4 z = quatre_normales(k0, k1, c, NORMALES);
        const uint4 ma = philox(k0, k1, c, AMPLEURS, 0, 0);
        for (int j = 0; j < 4; ++j) {
            const int g = 4 * c + j;
            if (g >= TAILLE) break;
            if (code[g] == CATEGORIEL) continue;  // la boucle des genes discrets les ecrit
            float v = x[g];
            if (g < 4) {
                v = sigma[g];
            } else if (code[g] == REEL || code[g] == ENTIER) {
                const float u = uniforme(mot(ma, j));
                const float ampleur = expf(__fadd_rn(__fmul_rn(u, (float)etendue_ampleur), (float)debut_ampleur));
                v = __fadd_rn(v, __fmul_rn(__fmul_rn(force[groupe[g]], ampleur), composante(z, j)));
                if (circulaire[g]) {
                    const float reste = fmodf(v, 1.f);  // torch.remainder : le reste prend le signe du diviseur
                    v = reste != 0.f && reste < 0.f ? __fadd_rn(reste, 1.f) : reste;
                } else {
                    v = borner(v);
                }
            }
            y[g] = v;
        }
    }
    for (int d = threadIdx.x; d < ND; d += blockDim.x) {
        const int g = discrets[d];
        const float u1 = uniforme(mot(philox(k0, k1, d / 4, UNIFORMES, 0, 0), d % 4));
        const float u2 = uniforme(mot(philox(k0, k1, d / 4, UNIFORMES_BIS, 0, 0), d % 4));
        const float xd = x[g];
        y[g] = u1 < (float)proba_categoriel ? floorf(__fmul_rn(u2, categories[g])) : xd;
    }
    __syncthreads();
    if (threadIdx.x == 0) ordonner(y, paires);
}
