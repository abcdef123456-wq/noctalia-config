"""Exécuter la découverte unittest du workflow sous l’utilisateur ci, dans son conteneur."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


SUITES = ()


def decouvrir(racine):
    # Aucun import du dépôt dans le coordinateur : tests/__init__.py pose son faux
    # sysfs, ses XDG et son journal une fois par interpréteur, sous son propre TMPDIR.
    global SUITES
    tmp = Path(racine) / str(os.getpid())
    tmp.mkdir(mode=0o700)
    os.environ.update(TMPDIR=str(tmp), RUNNER_TEMP=str(tmp))
    tempfile.tempdir = None
    SUITES = tuple(unittest.TestLoader().discover("tests", top_level_dir="."))


def tailles():
    return [suite.countTestCases() for suite in SUITES]


def executer(index, total, taille):
    if len(SUITES) != total or SUITES[index].countTestCases() != taille:
        raise RuntimeError("La découverte unittest diffère entre deux processus")
    # Ne pas reconstruire les tests à partir de leurs identifiants : garder les
    # suites de découverte, y compris load_tests, les fixtures et les erreurs d’import.
    journal = io.StringIO()
    resultat = unittest.TextTestRunner(stream=journal, verbosity=0).run(SUITES[index])
    erreur = None if resultat.wasSuccessful() else journal.getvalue()[-8192:]
    return resultat.testsRun, len(resultat.skipped), erreur


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=5,
                        help="processus unittest simultanés (défaut : 5)")
    args = parser.parse_args()
    executes = ignores = 0
    erreurs = []
    with tempfile.TemporaryDirectory(prefix="ut-") as racine:
        with ProcessPoolExecutor(args.workers, initializer=decouvrir, initargs=(racine,)) as pool:
            nombres = pool.submit(tailles).result()
            # Les grosses suites partent en premier ; un processus qui se libère
            # prend le module suivant au lieu d’attendre un lot statique déséquilibré.
            ordre = sorted(range(len(nombres)), key=nombres.__getitem__, reverse=True)
            taches = [pool.submit(executer, i, len(nombres), nombres[i]) for i in ordre]
            for tache in as_completed(taches):
                n, s, erreur = tache.result()
                executes += n
                ignores += s
                if erreur is not None:
                    erreurs.append(erreur)
    for erreur in erreurs:
        print(erreur, file=sys.stderr, flush=True)
    print(f"Bilan unittest : {executes} exécutés, {ignores} ignorés", flush=True)
    if erreurs:
        return 1
    return 0 if executes or ignores else 5  # même statut que unittest sans tests


if __name__ == "__main__":
    sys.exit(main())
