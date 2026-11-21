"""
Library of transport scenarios for robotic platforms coordinated over Meshtastic.

Each scenario is a :class:`~meshrtc.sim.Config` with a short Ukrainian/English
description. Run one with ``run_scenario("S04")`` or iterate over ``SCENARIOS``.
"""
from __future__ import annotations

import copy
from dataclasses import replace

from . import protocol as pr
from .sim import Config, Sim, run_paired

SCENARIOS = {
    "S01": dict(
        cfg=Config(name="S01", title="Medicine delivery, full connectivity (C0)",
                   H=2, k=4, b=0.0, soc0=0.8, p_close=0, gnss_denied=False, snow=1.2, temp=-3,
                   tasks=[dict(site="R3", alt="R6")], seed=11),
        ua="Доставка ліків (інсулін) до пункту R3; стільниковий зв'язок і mesh доступні (режим C0). "
           "ЦКК надсилає контракт TSK, робот звітує квитанцією RCP.",
        en="Insulin to recipient R3 with cellular and mesh available (regime C0)."),
    "S02": dict(
        cfg=Config(name="S02", title="Site closure and re-targeting over the mesh (C1)",
                   H=48, k=4, b=0.0, soc0=0.75, p_close=0, cell_off=True, gnss_denied=False, snow=1.3, temp=-6,
                   tasks=[dict(site="R2", alt="R7")], closures=[dict(t=12.0, site="R2", alt="R7")], seed=12),
        ua="Мобільний зв'язок зник (C1). Пункт R2 закривається на 12-й хв; ЦКК розсилає CLS R2 ALT R7; "
           "SFC перевіряє енергію і перенацілюється (DEC RTG).",
        en="Cellular lost; R2 closes, CC broadcasts CLS, the SFC re-targets to R7 if feasible."),
    "S03": dict(
        cfg=Config(name="S03", title="Unknown blockages: sense, report, detour",
                   H=24, k=4, b=0.15, cc_known_frac=0.0, soc0=0.7, p_close=0, gnss_denied=False, snow=1.4, temp=-5,
                   tasks=[dict(site="R8", alt="R1")], n_robots=1, seed=13),
        ua="15 % ділянок перекрито (завали, повалені дерева), ЦКК про них не знає. Робот виявляє перекриття "
           "сенсорами, надсилає BLK і переплановує маршрут.",
        en="Clustered blockages unknown to the CC; the robot senses them, reports BLK and replans."),
    "S04": dict(
        cfg=Config(name="S04", title="Isolated robot with low charge (C3)",
                   H=72, k=0, b=0.05, soc0=0.42, p_close=0, jam_mesh=True, cell_off=True, gnss_denied=False,
                   snow=1.6, temp=-12, tasks=[dict(site="R8", alt="R1")], seed=14),
        ua="Повна ізоляція (C3): мережа і mesh недоступні, заряд 42 %, сніг. Порівняння S1 / S2 / S3: "
           "зупинка при втраті зв'язку, фіксований маршрут, SFC.",
        en="Full isolation, 42 % charge, heavy snow; compare S1, S2 and S3."),
    "S05": dict(
        cfg=Config(name="S05", title="GNSS denied: localisation guard and cautious mode",
                   H=24, k=4, b=0.05, soc0=0.8, p_close=0, gnss_denied=True, snow=1.3, temp=-4,
                   tasks=[dict(site="R6", alt="R2")], seed=15),
        ua="Супутникова навігація недоступна. Невизначеність положення σ зростає; SFC переходить у "
           "обережний режим (κ = 0.6) і зупиняється з маяком, якщо загубився на 3 перехрестях.",
        en="GNSS denied; sigma grows, the SFC slows down (kappa = 0.6) and beacon-stops if lost."),
    "S06": dict(
        cfg=Config(name="S06", title="Fleet shift with intermittent contact (C2): centralized vs agentic",
                   fleet=True, n_robots=4, H=48, k=2, b=0.05, p_close=0, shift=480, seed=516),
        ua="Зміна 8 год, 4 роботи, заявки REQ від пунктів. Централізоване диспетчування проти агентного "
           "(запасні одиниці, DTN-підбір заявок, аукціон BID/LSE).",
        en="Eight-hour shift, four robots; centralized dispatch vs agentic market with DTN."),
    "S07": dict(
        cfg=Config(name="S07", title="Relay UGV with a 10 m telescopic mast restores coverage",
                   H=72, k=0, b=0.05, soc0=0.7, p_close=0, cell_off=True, gnss_denied=False, relay=True,
                   snow=1.3, temp=-5, tasks=[dict(site="R7", alt="R2")], seed=17),
        ua="Без ретрансляторів і мобільного зв'язку. Планувальник двійника надсилає RLY роботу-ретранслятору, "
           "який піднімає щоглу 10 м біля маршруту до R7; квитанції доходять швидше.",
        en="No repeaters, no cellular; the twin planner sends RLY to a relay UGV with a mast."),
    "S08": dict(
        cfg=Config(name="S08", title="Water multi-drop with heavy load: drop-stop decisions",
                   H=24, k=4, b=0.05, soc0=0.55, p_close=0, gnss_denied=False, snow=1.7, temp=-14,
                   payload_kg=30, tasks=[dict(site="R5", alt="R1"), dict(site="R1", alt="R8"),
                                         dict(site="R3", alt="R8")], seed=18),
        ua="Розвезення питної води на три пункти, вантаж 30 кг, -14 °C. SFC відкидає останню зупинку "
           "(DEC DRP), якщо разом із поверненням вона не вкладається в енергетичний бюджет.",
        en="Drinking water to three sites, 30 kg; the SFC drops the last stop when infeasible."),
    "S09": dict(
        cfg=Config(name="S09", title="Airtime surge: periodic vs event-driven reporting",
                   H=48, k=4, b=0.0, soc0=0.8, p_close=0, cell_off=True, gnss_denied=False, n_robots=6,
                   reporting="periodic", preset="MEDIUM_FAST", tasks=[dict(site=f"R{i}", alt="R1") for i in (2, 3, 4, 5, 6, 7)],
                   events=[dict(t=60.0, kind="cmd", cmd=pr.RPT(0))], seed=19),
        ua="Шість роботів звітують щохвилини з підтвердженням, шлюз ЦКК вичерпує 1 % duty cycle. "
           "Комунікаційний агент (Comms steward) розсилає RPT 0 - перехід на звіти за подіями.",
        en="Six robots with acknowledged 1-min reports; the comms steward switches to event-driven."),
    "S10": dict(
        cfg=Config(name="S10", title="Operator recall and risk dial (human on the loop)",
                   H=24, k=4, b=0.05, soc0=0.8, p_close=0, gnss_denied=False, snow=1.3, temp=-5,
                   tasks=[dict(site="R7", alt="R2")],
                   events=[dict(t=5.0, kind="cmd", cmd=pr.ZSET(2.33)),
                           dict(t=20.0, kind="cmd", cmd=pr.HLD(1, 10), dst="U1"),
                           dict(t=45.0, kind="cmd", cmd=pr.RTB(1, 1), dst="U1")], seed=20),
        ua="Оператор підвищує рівень ризику (ZSET 233), тимчасово утримує робота (HLD) і відкликає "
           "його до пункту P1 (RTB) - людина в контурі керування.",
        en="Operator raises the risk dial, holds the robot, then recalls it to P1."),
}


def get(sid: str) -> Config:
    return copy.deepcopy(SCENARIOS[sid]["cfg"])


def run_scenario(world, sid: str, strategy: str = None, **overrides) -> Sim:
    cfg = get(sid)
    if overrides:
        cfg = replace(cfg, **overrides)
    return Sim(world, cfg, strategy=strategy).run()


def run_scenario_paired(world, sid: str, strategies=("S1", "S2", "S3"), **overrides):
    cfg = get(sid)
    if overrides:
        cfg = replace(cfg, **overrides)
    return run_paired(world, cfg, strategies)
