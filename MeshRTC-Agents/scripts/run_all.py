"""Reproduce every figure and table without Jupyter:  python scripts/run_all.py
(executes the notebook headlessly if nbconvert is available, otherwise runs the core experiments)."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

nb = os.path.join("notebooks", "MeshRTC_Agents_Colab.ipynb")
try:
    subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                    "--ExecutePreprocessor.timeout=1800", "--output", "MeshRTC_Agents_Colab.executed.ipynb", nb],
                   check=True)
    print("executed notebook -> notebooks/MeshRTC_Agents_Colab.executed.ipynb, figures -> figures/")
except Exception as e:  # pragma: no cover
    print("nbconvert unavailable (", e, ") - running core experiments only")
    import matplotlib
    matplotlib.use("Agg")
    from meshrtc.world import World
    from meshrtc import experiments as ex, viz
    viz.setup_style()
    w = World()
    os.makedirs("figures", exist_ok=True)
    df = ex.single_missions(w, reps=8)
    print(ex.summary_table(df))
    ex.plot_single(df).savefig("figures/mc_single_missions.png")
    dfF = ex.fleet_experiment(w, reps=10)
    print(dfF.groupby(["policy", "k"])[["service", "aware_med", "lat_med"]].mean().round(2))
    ex.plot_fleet(dfF).savefig("figures/fleet_policies.png")
