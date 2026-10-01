"""Benchmark final : le bloc de test, ouvert une seule fois.

    python -m evolution.benchmark runs/<reel> --a-blanc runs/<a-blanc> [--hasard runs/<hasard>]

Le champion du Pantheon passe le test trimestre par trimestre, aux couts de reference, avec le buy and hold,
le champion aleatoire, le champion a blanc et, s'il est fourni, celui de la recherche aleatoire. Leurs flux
d'ordres sont rejoues dans le grand livre du moteur. Le dossier benchmark/ du run reel sert de verrou :
s'il existe, le test a deja ete ouvert et rien n'est relance.
"""
import argparse
import math
import statistics
import warnings
from decimal import Decimal
from pathlib import Path

warnings.filterwarnings("ignore", message="Failed to initialize NumPy")  # PyTorch s'en passe tres bien
import torch  # noqa: E402

from evolution import checkpoint, gpu, mesures  # noqa: E402
from evolution.bilan import bilans  # noqa: E402
from evolution.config import lire  # noqa: E402
from evolution.contexte import Contexte, maintenant, manifeste, preparer, reference  # noqa: E402
from evolution.data import MILLION, Fenetre, trimestres  # noqa: E402
from evolution.evaluation import COMPLETS_MAX  # noqa: E402
from evolution.fitness import rangs_contre  # noqa: E402
from evolution.rejeu import consigner  # noqa: E402


def achat_conserve(ctx: Contexte, fenetre: Fenetre) -> dict:
    """Buy and hold d'un trimestre : achat a l'ouverture de sa premiere barre, vente a la cloture de sa
    derniere, glissement et frais compris ; capital marque a chaque cloture entre les deux.
    """
    hist, g, f = ctx.hist, fenetre.glissement, fenetre.frais
    debut, fin = fenetre.debut + fenetre.prechauffage, fenetre.fin
    pas = float(ctx.config.pas_de_prix)
    achat = -(-int(hist.ouverture[debut]) * (MILLION + g) // MILLION) * pas
    capital = float(ctx.config.capital_initial)
    quantite = capital / (achat * (1 + f / MILLION))
    clotures = hist.cloture[debut:fin].double() * pas
    marques = (quantite * clotures).tolist()
    vente = int(hist.cloture[fin - 1]) * (MILLION - g) // MILLION * pas
    marques[-1] = quantite * vente * (1 - f / MILLION)
    return {"capital_final": marques[-1], "marques": marques}


def serie_capital(capital0: float, marques: list[float]) -> dict:
    """Rendement, drawdown maximal et moments des rendements horaires d'une courbe de capital."""
    precedent, pic, pire, sommes = capital0, capital0, 0.0, [0.0] * 4
    for marque in marques:
        r = marque / precedent - 1
        for k in range(4):
            sommes[k] += r ** (k + 1)
        pic = max(pic, marque)
        pire = max(pire, 1 - marque / pic)
        precedent = marque
    return {"rendement": marques[-1] / capital0 - 1, "drawdown": pire, "sommes": sommes, "heures": len(marques)}


def metriques_trades(trades: list, ouvertures: list[Decimal]) -> dict:
    """Taux de reussite, seuil d'equilibre, esperance nette par trade et son t."""
    resultats = [float(t.net / capital) for t, capital in zip(trades, ouvertures)]
    gains = [float(t.net) for t in trades if t.net > 0]
    pertes = [float(t.net) for t in trades if t.net <= 0]
    n = len(resultats)
    moyenne = sum(resultats) / n if n else 0.0
    ecart = statistics.stdev(resultats) if n >= 2 else 0.0
    gain_moyen = sum(gains) / len(gains) if gains else 0.0
    perte_moyenne = sum(pertes) / len(pertes) if pertes else 0.0
    return {
        "trades": n,
        "taux_de_reussite": len(gains) / n if n else 0.0,
        "gain_moyen": gain_moyen,
        "perte_moyenne": perte_moyenne,
        "seuil_equilibre": 1 / (1 + gain_moyen / abs(perte_moyenne)) if perte_moyenne else math.nan,
        "esperance_par_trade": moyenne,
        "t_esperance": moyenne / (ecart / math.sqrt(n)) if n >= 2 and ecart > 0 else 0.0,
        "frais": sum(float(t.fees) for t in trades),
    }


def ensemble(parties: list[dict], capital0: float) -> dict:
    """Trimestres mis bout a bout : rendements chaines, pire drawdown, Sharpe sur toutes les heures."""
    sommes = [sum(p["sommes"][k] for p in parties) for k in range(4)]
    heures = sum(p["heures"] for p in parties)
    moyenne, ecart, asymetrie, kurtosis = mesures.moments(sommes, heures)
    sr = mesures.sharpe(moyenne, ecart)
    return {
        "rendement_chaine": math.prod(1 + p["rendement"] for p in parties) - 1,
        "drawdown_max": max(p["drawdown"] for p in parties),
        "sharpe_annualise": mesures.sharpe_annualise(moyenne, ecart),
        "psr": mesures.psr(sr, heures, asymetrie, kurtosis),
        "capital_initial_par_trimestre": capital0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark final sur le bloc de test, ouvert une seule fois.")
    parser.add_argument("reel", type=Path, help="dossier du run reel")
    parser.add_argument("--a-blanc", type=Path, dest="a_blanc", help="dossier du run a blanc de ce run")
    parser.add_argument("--hasard", type=Path, help="dossier de la recherche aleatoire de ce run")
    parser.add_argument("--sans-a-blanc", action="store_true", dest="sans_a_blanc",
                        help="ouvrir le test sans champion a blanc : l'ecart au hasard manquera pour toujours")
    args = parser.parse_args()
    verrou = args.reel / "benchmark"
    if verrou.exists():
        raise SystemExit(f"Le bloc de test a deja ete ouvert : voir {verrou / 'rapport.json'}")
    etat = checkpoint.lire(args.reel / "etat.json")
    if etat["mode"] != "reel" or not etat["pantheon"]:
        raise SystemExit(f"{args.reel} n'est pas un run reel avec un Pantheon")
    if args.a_blanc is None and not args.sans_a_blanc:
        raise SystemExit("Le test ne s'ouvre qu'une fois : lancez d'abord le run a blanc (--a-blanc), "
                         "ou confirmez --sans-a-blanc.")
    autres = {}
    for option, chemin in (("a-blanc", args.a_blanc), ("hasard", args.hasard)):
        if chemin is None:
            continue
        autre = checkpoint.lire(chemin / "etat.json")
        if autre["mode"] != option or Path(autre["source"]).resolve() != args.reel.resolve():
            raise SystemExit(f"{chemin} n'est pas le run {option} de {args.reel}")
        if autre["generation"] < autre["generations_max"]:
            raise SystemExit(f"{chemin} n'est pas termine : {autre['generation']}/{autre['generations_max']} generations")
        if autre["generations_max"] != etat["generation"]:
            raise SystemExit(f"{chemin} compte {autre['generations_max']} generations, le run reel "
                             f"{etat['generation']} : relancez-le sur le run reel tel qu'il est.")
        autres[option] = autre
    verrou.mkdir()  # a partir d'ici, le test est ouvert
    appareil = gpu.preparer()
    config = lire((args.reel / "config.toml").read_text(encoding="utf-8"))
    ctx = preparer(config, appareil, test=True, taille_paquet=etat["taille_paquet"])
    checkpoint.ecrire(verrou / "manifest.json", manifeste(ctx, "benchmark", args.reel.as_posix()))
    quarts = trimestres(ctx.hist, config, config.debut_test, None)
    print("Bloc de test :", ", ".join(f"{q.nom} ({q.longueur} barres)" for q in quarts), flush=True)
    notes_ref = reference(ctx, quarts)
    bots = {"champion": etat["pantheon"][0], "champion aleatoire": etat["champion_aleatoire"]}
    if "a-blanc" in autres:
        bots["champion a blanc"] = autres["a-blanc"]["pantheon"][0]
    if "hasard" in autres:
        bots["champion de la recherche aleatoire"] = autres["hasard"]["pantheon"][0]
    genomes = torch.stack([checkpoint.tenseur(b["genome"]) for b in bots.values()])
    traces = ctx.evaluateur.traces(genomes, quarts)
    unite = float(ctx.evaluateur.principal.unite)
    bilans_ = bilans(traces, quarts, ctx.capital0, unite, config)
    capital0 = float(config.capital_initial)
    rapport = {"date": maintenant(), "run": args.reel.as_posix(),
               "trimestres": [{"nom": q.nom, "barres": q.longueur} for q in quarts], "bots": {}}
    for position, (nom, bot) in enumerate(bots.items()):
        res, b = traces[position // COMPLETS_MAX], position % COMPLETS_MAX
        parties, trades, ouvertures, conformes, ecarts = [], [], [], [], []
        for w, q in enumerate(quarts):
            trace = {cle: t[:, b, w] for cle, t in res.trace.items()}
            r = consigner(ctx.hist, q, trace, config, bot["id"], ctx.symbole, verrou / nom.replace(" ", "_") / q.nom)
            conformes.append(r.conforme)
            ecarts.append(str(r.ecart_max))
            trades += r.trades
            ouvertures += r.capitaux_ouverture
            marques = [float(Decimal(int(c)) * ctx.evaluateur.principal.unite)
                       for c in trace["capital"][q.prechauffage:q.prechauffage + q.longueur]]
            parties.append(serie_capital(capital0, marques))
        bilan = bilans_[position]
        rapport["bots"][nom] = {
            "id": bot["id"],
            "note_test": bilan.note,
            "rang_centile_reference": float(rangs_contre(torch.tensor([bilan.note], dtype=torch.float64), notes_ref)[0]),
            "par_trimestre": [{"nom": q.nom, "rendement": p["rendement"], "drawdown": p["drawdown"],
                               "trades": t, "sorties": s, "rotation": rot}
                              for q, p, t, s, rot in zip(quarts, parties, bilan.trades, bilan.sorties, bilan.rotation)],
            **ensemble(parties, capital0),
            **metriques_trades(trades, ouvertures),
            "rotation_du_capital": sum(bilan.rotation),
            "sorties": {raison: sum(s[raison] for s in bilan.sorties) for raison in bilan.sorties[0]},
            "rejeu_conforme": all(conformes),
            "rejeu_ecarts_max": ecarts,
        }
    parties = []
    for q in quarts:
        bh = achat_conserve(ctx, q)
        parties.append(serie_capital(capital0, bh["marques"]))
    rapport["bots"]["buy and hold"] = {
        "par_trimestre": [{"nom": q.nom, "rendement": p["rendement"], "drawdown": p["drawdown"], "trades": 1}
                          for q, p in zip(quarts, parties)],
        **ensemble(parties, capital0),
    }
    champion = etat["pantheon"][0]
    detail = champion["detail"]
    essais = list(etat["validations"].values())
    rapport["validation"] = {
        "note_champion": champion["note"],
        "bots_evalues_en_validation": len(essais),
        "sharpe_annualise_champion": detail["sharpe_annualise"],
        "deflated_sharpe_ratio": mesures.dsr(detail["sharpe"], detail["heures"], detail["asymetrie"],
                                             detail["kurtosis"], essais),
        "bots_evalues_en_entrainement": etat["bots_evalues"],
    }
    if "a-blanc" in autres:
        blanc = autres["a-blanc"]["pantheon"][0]["note"]
        rapport["validation"]["note_champion_a_blanc"] = blanc
        rapport["validation"]["ecart_au_hasard"] = champion["note"] - blanc
    rapport["conforme"] = rapport["bots"]["champion"]["rejeu_conforme"]
    checkpoint.ecrire(verrou / "rapport.json", rapport)
    afficher(rapport)
    print(f"Rapport : {verrou / 'rapport.json'}", flush=True)


def afficher(rapport: dict) -> None:
    print(f"\n{'':38s} {'rendement':>10s} {'drawdown':>9s} {'Sharpe':>7s} {'PSR':>6s} {'trades':>7s} {'note':>6s} {'centile':>8s}")
    for nom, b in rapport["bots"].items():
        print(f"{nom:38s} {b['rendement_chaine']:>10.2%} {b['drawdown_max']:>9.2%} {b['sharpe_annualise']:>7.2f} "
              f"{b['psr']:>6.2f} {b.get('trades', len(b['par_trimestre'])):>7d} {b.get('note_test', math.nan):>6.3f} "
              f"{b.get('rang_centile_reference', math.nan):>8.2%}")
    v = rapport["validation"]
    print(f"\nValidation : note du champion {v['note_champion']:.4f}, Deflated Sharpe Ratio {v['deflated_sharpe_ratio']:.3f} "
          f"sur {v['bots_evalues_en_validation']} bots evalues en validation.")
    if "ecart_au_hasard" in v:
        print(f"Ecart au hasard : {v['ecart_au_hasard']:+.4f} (champion a blanc : {v['note_champion_a_blanc']:.4f}).")
    print("Rejeu exact du champion :", "conforme" if rapport["conforme"] else "NON CONFORME")


if __name__ == "__main__":
    main()
