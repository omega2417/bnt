"""Virtual testbed: emulated physical plant + measurement chain + ESP32 edge
guard + MQTT transport + digital twin + EMS + independent REF logger +
network availability probe. One call of run() = one run_id.

Loop per 1-s step [t, t+1):
  a) PC acts at t (heartbeat, stale detection, EMS decision, command send);
  b) down-link messages arriving in the step are handled by the edge at their
     exact arrival time, ACKs are sent up;
  c) up-link messages (telemetry, ACK) arriving in the step are processed;
  d) plant physics over the step, auxiliary power weighted by the fraction of
     the step during which the relay was actually closed;
  e) 10 Hz sampling, 1 Hz telemetry publication, REF logging, service probe.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

import numpy as np

from . import ems as ems_mod
from .battery import BatteryPlant
from .edge_guard import EdgeGuard, RUNNING
from .forecast import CausalGenForecaster, DemandForecaster
from .sensors import make_channel, make_temp
from .transport import Channel
from .twin import Twin

SAMPLES_PER_S = 10


@dataclass
class BenchInstance:
    """A physical bench unit: hidden truth + calibrated instruments (from E00/E09)."""
    hw: dict
    truth: object
    channels: dict
    temp: object
    q_ref_ah: float
    q_m1_ah: float
    eta_q_ref: float
    eta_crit: float
    eta_aux: float
    seed: int


@dataclass
class Scenario:
    sid: str
    duration_s: int
    p_gen_avail: np.ndarray
    p_crit_term: np.ndarray
    aux_sched: np.ndarray
    soc0: float
    temp_batt_c: float = 22.0
    blackouts: list = field(default_factory=list)       # (t0, t1, 'up'|'down'|'both')
    sensor_faults: list = field(default_factory=list)   # (t0, t1, kind, param)
    stale_command_test_at: float | None = None
    stop_soc_ref: float | None = 0.20
    note: str = ""


def _lat_stats(x):
    if not x:
        return {"n": 0}
    a = np.asarray(x) * 1000
    return {"n": len(a), "median_ms": float(np.median(a)), "p95_ms": float(np.percentile(a, 95)),
            "p99_ms": float(np.percentile(a, 99)), "max_ms": float(a.max())}


def _inject_fault(m: dict, kind: str, param, state: dict) -> dict:
    m = dict(m)
    if kind == "offset":
        m["i_batt_a"] += param
    elif kind == "stuck":
        state.setdefault("stuck", m["i_batt_a"])
        m["i_batt_a"] = state["stuck"]
    elif kind == "missing":
        m[param] = None
    elif kind == "impossible":
        m["v_batt_v"] = param
    elif kind == "sign":
        m["i_batt_a"] = -m["i_batt_a"]
    return m


def run(bench: BenchInstance, sc: Scenario, policy_name: str, pcfg: dict, *, repeat: int = 0,
        mode: str = "sil_hw_emulated", seed: int = 0, keep_series: bool = True, run_id: str | None = None) -> dict:
    hw = bench.hw
    tm = hw["timing"]
    rng = np.random.default_rng(seed)
    for ch in bench.channels.values():   # fresh noise stream per run, same calibrated unit
        ch.rng = rng
    bench.temp.rng = rng
    run_id = run_id or f"20260929_{sc.sid}_{policy_name}_R{repeat:02d}_EMU"
    boot_id = uuid.UUID(int=int(rng.integers(0, 2**63))).hex[:12]

    plant = BatteryPlant(truth=bench.truth, z=sc.soc0, temp_c=sc.temp_batt_c,
                         v_uv=hw["battery"]["bms_undervoltage_v"], v_ov=hw["battery"]["bms_overvoltage_v"],
                         i_ch_max=hw["battery"]["max_charge_current_a"])
    clk_unc = tm["clock_uncertainty_ms"] / 1000
    edge = EdgeGuard(run_id, boot_id, mode, clock_offset_s=float(rng.uniform(-clk_unc, clk_unc)),
                     clock_uncertainty_s=clk_unc, stale_s=tm["telemetry_stale_s"])
    edge.self_test(True)
    up, down = Channel(hw["network"], rng), Channel(hw["network"], rng)
    for t0, t1, d in sc.blackouts:
        if d in ("up", "both"):
            up.blackouts.append((t0, t1, "up"))
        if d in ("down", "both"):
            down.blackouts.append((t0, t1, "down"))

    # Initial state: established by the preparation procedure (REF), entered in the protocol.
    soc_ref = float(np.clip(sc.soc0 + rng.normal(0, 0.004), 0, 1))
    soc_ref0 = soc_ref
    twin = Twin(q_model_ah=bench.q_m1_ah, eta_q_model=1.0, r0_model=0.018, z_post=soc_ref0)
    policy = ems_mod.make_policy(policy_name, pcfg)
    gen_fc, dem_fc = CausalGenForecaster(), DemandForecaster()
    oracle = policy_name == "C_oracle"

    n = sc.duration_s
    v_cv = hw["generation_g1"]["cv_setpoint_v"]
    p_other = hw["other_bus_load_w"]
    aux_term_w = hw["aux_branch"]["p_terminal_w"]
    sw_delay = (hw["aux_branch"]["relay_operate_ms"] + hw["aux_branch"]["led_softstart_ms"]) / 1000
    svc_fail_p = hw["network"]["service_check_fail_prob"]

    relay_on = False
    relay_events = []            # (t_switch, new_state)
    pending = {}                 # command_id -> dict
    commands = []
    seen_keys = set()
    last_rx_t, last_seq_t = 0.0, None
    stale_flag = False
    fallback_sent = False
    last_commanded = None
    events = [{"t": 0.0, "event_type": "RUN_START", "value": soc_ref0}]
    fault_state = {}
    seq = 0
    stop_reason, t_stop = "completed", None

    keys = ("t", "soc_true", "soc_ref", "soc_prior", "soc_post", "v_batt", "i_batt", "i_ref", "p_gen_avail", "p_gen",
            "p_crit_term", "p_aux_term", "aux_sched", "aux_cmd", "relay", "pred_min", "valid", "residual_w", "service_ok")
    S = {k: [] for k in keys}
    acc = {"e_crit_dem": 0.0, "e_crit_srv": 0.0, "e_aux_dem": 0.0, "e_aux_srv": 0.0, "lolh_crit_h": 0.0, "lolh_tot_h": 0.0,
           "e_gen": 0.0, "e_curt": 0.0, "e_ref_dis": 0.0, "e_ref_ch": 0.0, "svc_n": 0, "svc_fail": 0, "svc_streak": 0,
           "svc_streak_max": 0, "unknown_s": 0.0, "tel_expected": 0, "tel_valid": 0, "dups": 0}
    soc_err, prior_err, true_err = [], [], []
    last_pred = None
    n_relay_switch = 0
    min_soc_ref = soc_ref
    res_sum = res_sq = 0.0
    res_n = 0
    edge.start(0.0)

    def send_command(t_pc, action, reason, retry_of=None):
        cid = f"{run_id}-c{len(commands):05d}"
        pc_utc = t_pc  # PC clock is the UTC reference in the emulation
        cmd = {"schema_version": "1.0", "mode": mode, "source": "ems", "run_id": run_id, "boot_id_target": boot_id,
               "command_id": cid, "action": action, "issued_at_utc": pc_utc, "expires_at_utc": pc_utc + tm["command_ttl_ms"] / 1000,
               "ttl_ms": tm["command_ttl_ms"], "reason": reason, "source_seq": seq}
        rec = {"command_id": cid, "action": action, "reason": reason, "sent": t_pc, "ack": None, "accepted": None,
               "reject_reason": "", "effect": None, "retry_of": retry_of, "decision_t": t_pc, "effect_kind": None}
        commands.append(rec)
        pending[cid] = rec
        down.send(t_pc, "dt/node01/command", cmd, "down")
        return rec

    for k in range(n):
        t = float(k)
        # ---------------- a) PC side at t ----------------
        age = t - last_rx_t
        if age > tm["telemetry_stale_s"]:
            if not stale_flag:
                stale_flag = True
                events.append({"t": t, "event_type": "TELEMETRY_STALE", "value": age})
            if not fallback_sent:
                send_command(t, "SET_AUX_OFF", "stale_fallback")
                fallback_sent, last_commanded = True, False
        elif stale_flag:
            stale_flag, fallback_sent = False, False
            events.append({"t": t, "event_type": "TELEMETRY_RESTORED", "value": age})
        down.send(t, "dt/node01/health", {"run_id": run_id, "reconciled": not stale_flag}, "down")

        if sc.stale_command_test_at is not None and abs(t - sc.stale_command_test_at) < 0.5:
            old = {"schema_version": "1.0", "mode": mode, "source": "ems", "run_id": run_id, "boot_id_target": boot_id,
                   "command_id": f"{run_id}-stale", "action": "SET_AUX_ON", "issued_at_utc": t - 30,
                   "expires_at_utc": t - 28, "ttl_ms": 2000, "reason": "E06_stale_test", "source_seq": -1}
            commands.append({"command_id": old["command_id"], "action": "SET_AUX_ON", "reason": "E06_stale_test", "sent": t,
                             "ack": None, "accepted": None, "reject_reason": "", "effect": None, "retry_of": None, "decision_t": t})
            pending[old["command_id"]] = commands[-1]
            down.send(t, "dt/node01/command", old, "down")
            wrong = dict(old, command_id=f"{run_id}-oldrun", run_id="20260928_E06_C1_R00_EMU", expires_at_utc=t + 2)
            commands.append({"command_id": wrong["command_id"], "action": "SET_AUX_ON", "reason": "E06_wrong_run", "sent": t,
                             "ack": None, "accepted": None, "reject_reason": "", "effect": None, "retry_of": None, "decision_t": t})
            pending[wrong["command_id"]] = commands[-1]
            down.send(t, "dt/node01/command", wrong, "down")

        # retry once after ACK timeout
        for rec in list(pending.values()):
            if rec["ack"] is None and t - rec["sent"] > tm["ack_timeout_s"] and rec["retry_of"] is None \
                    and rec["reason"] not in ("E06_stale_test", "E06_wrong_run"):
                rec["reject_reason"] = "ack_timeout"
                pending.pop(rec["command_id"], None)
                if not stale_flag:
                    send_command(t, rec["action"], rec["reason"], retry_of=rec["command_id"])

        sched_now = bool(sc.aux_sched[k])
        if k % tm["ems_period_s"] == 0 and not stale_flag:
            soc_now = twin.z_post
            nh = int(pcfg["C2"]["horizon_s"] // pcfg["C2"]["step_s"])
            st = pcfg["C2"]["step_s"]
            idx = np.minimum(k + np.arange(nh) * st, n - 1)
            if oracle:
                gfc = np.array([sc.p_gen_avail[i:i + st].mean() for i in idx])
            else:
                gfc = gen_fc.forecast(nh)
            aux_bus_sched = sc.aux_sched[idx].astype(float) * aux_term_w / 0.90
            crit_fc, aux_fc = dem_fc.forecast(nh, aux_bus_sched)
            d = policy.decide(t, soc_now, sched_now, twin=twin, gen_fc=gfc, load_crit_bus_fc=crit_fc, aux_sched_bus_fc=aux_fc)
            last_pred = d.predicted_min_soc
            if d.aux_on != last_commanded:
                send_command(t, "SET_AUX_ON" if d.aux_on else "SET_AUX_OFF", d.reason)
                last_commanded = d.aux_on
        elif (not sched_now) and last_commanded:
            send_command(t, "SET_AUX_OFF", "schedule_off")
            last_commanded = False
            policy.aux_state = False

        # ---------------- b) down-link at edge ----------------
        for t_arr, topic, payload in down.deliver(t + 1.0):
            if topic == "dt/node01/health":
                edge.heartbeat(t_arr, payload)
            elif topic == "dt/node01/command":
                before = edge.aux_out
                ack = edge.handle_command(t_arr + 0.002, payload)
                if edge.aux_out != before:
                    relay_events.append((t_arr + 0.002 + sw_delay, edge.aux_out, payload["command_id"]))
                up.send(t_arr + 0.002, "dt/node01/ack", ack, "up")
        # edge local tick with last known measurements
        before = edge.aux_out
        edge.tick(t + 0.5, plant.terminal_voltage(0.0), plant.temp_c, plant.bms_open)
        if edge.aux_out != before:
            relay_events.append((t + 0.5 + sw_delay, edge.aux_out, "local"))

        # ---------------- c) up-link at PC ----------------
        for t_arr, topic, payload in up.deliver(t + 1.0):
            if topic == "dt/node01/ack":
                rec = pending.get(payload["command_id"])
                if rec is not None and rec["ack"] is None:
                    rec["ack"], rec["accepted"], rec["reject_reason"] = t_arr, payload["accepted"], payload["reject_reason"]
                    if not payload["accepted"]:
                        pending.pop(payload["command_id"], None)
            elif topic == "dt/node01/telemetry":
                key = (payload["run_id"], payload["device_id"], payload["boot_id"], payload["seq"])
                if key in seen_keys:
                    acc["dups"] += 1
                    continue
                seen_keys.add(key)
                if t_arr - last_rx_t > 2.0 and k > 2:
                    acc["unknown_s"] += t_arr - last_rx_t - 1.0
                dt = 1.0 if last_seq_t is None else max(1e-3, payload["t_mono_s"] - last_seq_t)
                last_seq_t = payload["t_mono_s"]
                last_rx_t = t_arr
                m = payload
                for f0, f1, kind, param in sc.sensor_faults:
                    if f0 <= payload["t_mono_s"] < f1:
                        m = _inject_fault(m, kind, param, fault_state)
                r = twin.update(m, dt)
                acc["tel_valid"] += int(r["valid"])
                if r["valid"]:
                    gen_fc.observe(m["p_gen_bus_w"])
                    dem_fc.observe(m["p_crit_bus_w"])
                else:
                    events.append({"t": t_arr, "event_type": "INVALID_SAMPLE", "value": r["reason"]})
                # physical effect confirmation from M4
                for rec in pending.values():
                    if rec["accepted"] and rec["effect"] is None:
                        on = rec["action"] == "SET_AUX_ON"
                        now_on = payload["p_aux_bus_last_w"] > 0.5 * aux_term_w / 0.9
                        if now_on == on:
                            rec["effect"] = payload["aux_edge_ts"] if payload["aux_edge_ts"] is not None else payload["t_sample_s"]
                            rec["effect_kind"] = "edge" if payload["aux_edge_ts"] is not None else "state_confirmed"
                for cid in [c for c, r_ in pending.items() if r_["effect"] is not None]:
                    pending.pop(cid)

        # ---------------- d) physics over [t, t+1) ----------------
        step_ev = sorted([e for e in relay_events if t <= e[0] < t + 1.0])
        on_time = 0.0
        cur, tt = relay_on, t
        for ev in step_ev:
            if cur:
                on_time += ev[0] - tt
            cur, tt = ev[1], ev[0]
        if cur:
            on_time += t + 1.0 - tt
        # relay state at the 10 Hz sample instants (edge-local detection of the M4 edge)
        ts = t + (np.arange(SAMPLES_PER_S) + 1) / SAMPLES_PER_S
        st_arr = np.full(SAMPLES_PER_S, relay_on)
        for ev in step_ev:
            st_arr[ts >= ev[0]] = ev[1]
        aux_edge_ts = None
        prev = relay_on
        for j in range(SAMPLES_PER_S):
            if st_arr[j] != prev:
                aux_edge_ts = float(ts[j])
                prev = st_arr[j]
        switched = cur != relay_on
        if switched or step_ev:
            n_relay_switch += sum(1 for _ in step_ev)
        relay_on = cur
        relay_events = [e for e in relay_events if e[0] >= t + 1.0]
        p_crit_term = sc.p_crit_term[k] * (1 + rng.normal(0, 0.02))
        p_crit_bus = p_crit_term / bench.eta_crit
        p_aux_term = aux_term_w * on_time
        p_aux_bus = p_aux_term / bench.eta_aux
        p_loads = p_crit_bus + p_aux_bus + p_other
        if plant.bms_open:
            p_gen, i, v = 0.0, 0.0, plant.terminal_voltage(0.0)
            p_crit_term = p_aux_term = 0.0
        else:
            e = plant.ocv() - plant.v_p
            i_ch_allow = min(plant.i_ch_max, max(0.0, (v_cv - e) / plant.truth.r0))
            p_accept = p_loads + i_ch_allow * min(v_cv, e + i_ch_allow * plant.truth.r0)
            p_gen = min(sc.p_gen_avail[k], p_accept)
            i, v = plant.solve_current(p_loads - p_gen)
        plant.step(i, 1.0)
        acc["e_gen"] += p_gen / 3600
        acc["e_curt"] += (sc.p_gen_avail[k] - p_gen) / 3600
        crit_uns = sc.p_crit_term[k] - p_crit_term if plant.bms_open else 0.0
        aux_dem = aux_term_w if sc.aux_sched[k] else 0.0
        acc["e_crit_dem"] += sc.p_crit_term[k] / 3600
        acc["e_crit_srv"] += (sc.p_crit_term[k] - crit_uns) / 3600
        acc["e_aux_dem"] += aux_dem / 3600
        acc["e_aux_srv"] += min(aux_dem, p_aux_term) / 3600
        acc["lolh_crit_h"] += (crit_uns > pcfg["epsilon_p_w"]) / 3600
        acc["lolh_tot_h"] += ((crit_uns + aux_dem - min(aux_dem, p_aux_term)) > pcfg["epsilon_p_w"]) / 3600

        # ---------------- e) sampling, telemetry, REF, service ----------------
        V = np.full(SAMPLES_PER_S, v)
        ch = bench.channels
        i_m1, v_m1, sat1 = ch["M1"].sample(np.full(SAMPLES_PER_S, i), V)
        i_m0, v_m0, _ = ch["M0"].sample(np.full(SAMPLES_PER_S, p_gen / v if v > 0 else 0), V)
        i_m2, v_m2, _ = ch["M2"].sample(np.full(SAMPLES_PER_S, p_crit_bus / v if v > 0 else 0), V)
        p_aux_bus_samples = st_arr.astype(float) * (aux_term_w / bench.eta_aux) if not plant.bms_open else np.zeros(SAMPLES_PER_S)
        i_m4, v_m4, _ = ch["M4"].sample(p_aux_bus_samples / v if v > 0 else np.zeros(SAMPLES_PER_S), V)
        i_rf, v_rf, _ = ch["REF"].sample(np.full(SAMPLES_PER_S, i), V)
        temp = bench.temp.read(plant.temp_c)
        seq += 1
        acc["tel_expected"] += 1
        tel = {"schema_version": "1.0", "run_id": run_id, "device_id": "esp32s3-node01", "boot_id": boot_id, "seq": seq,
               "mode": mode, "t_mono_s": t + 1.0, "t_sample_s": t + 1.0, "ts_utc": t + 1.0 + edge.clock_offset_s,
               "v_batt_v": float(v_m1.mean()), "i_batt_a": float(i_m1.mean()), "i_batt_min": float(i_m1.min()),
               "i_batt_max": float(i_m1.max()), "n_samples": SAMPLES_PER_S, "sensor_saturation": bool(sat1.any()),
               "p_gen_bus_w": float((v_m0 * i_m0).mean()), "p_crit_bus_w": float((v_m2 * i_m2).mean()),
               "p_aux_bus_w": float((v_m4 * i_m4).mean()), "p_aux_bus_last_w": float(v_m4[-1] * i_m4[-1]),
               "aux_edge_ts": aux_edge_ts, "temp_batt_c": temp, "aux_out": edge.aux_out}
        up.send(t + 1.0, "dt/node01/telemetry", tel, "up")
        # REF logger (independent channel, independent capacity, local storage)
        i_ref = float(i_rf.mean())
        v_ref = float(v_rf.mean())
        if i_ref >= 0:
            soc_ref -= i_ref / (3600 * bench.q_ref_ah)
            acc["e_ref_dis"] += v_ref * i_ref / 3600
        else:
            soc_ref += bench.eta_q_ref * (-i_ref) / (3600 * bench.q_ref_ah)
            acc["e_ref_ch"] += -v_ref * i_ref / 3600
        # service probe (N1), independent power
        ok = (not plant.bms_open) and v >= hw["critical_branch"]["dcdc_min_input_v"] and rng.random() > svc_fail_p
        acc["svc_n"] += 1
        acc["svc_fail"] += int(not ok)
        acc["svc_streak"] = 0 if ok else acc["svc_streak"] + 1
        acc["svc_streak_max"] = max(acc["svc_streak_max"], acc["svc_streak"])

        soc_err.append(twin.z_post - soc_ref)
        true_err.append(soc_ref - plant.z)
        resid = tel["p_gen_bus_w"] + tel["v_batt_v"] * tel["i_batt_a"] - tel["p_crit_bus_w"] - tel["p_aux_bus_w"]
        res_sum += resid
        res_sq += resid * resid
        res_n += 1
        min_soc_ref = min(min_soc_ref, soc_ref)
        if keep_series and (k % 10 == 0 or switched):
            vals = (t + 1, plant.z, soc_ref, twin.prior(0.0), twin.z_post, v, i, i_ref, sc.p_gen_avail[k], p_gen, p_crit_term,
                    p_aux_term, int(sched_now), int(edge.aux_out), int(relay_on), last_pred, int(twin.valid_frac[0]), resid, int(ok))
            for kk, vv in zip(keys, vals):
                S[kk].append(vv)
        if sc.stop_soc_ref is not None and soc_ref <= sc.stop_soc_ref:
            stop_reason, t_stop = "stopped_limit", t + 1.0
            events.append({"t": t + 1.0, "event_type": "STOP_LIMIT_SOC_REF", "value": soc_ref})
            edge.stop("limit", t + 1.0)
            break
        if plant.bms_open:
            stop_reason, t_stop = "stopped_bms", t + 1.0
            break

    dur = (t_stop if t_stop else float(n))
    events.append({"t": dur, "event_type": "RUN_END", "value": stop_reason})
    err = np.asarray(soc_err) * 100
    terr = np.asarray(true_err) * 100
    acc_cmd = [c for c in commands if c["accepted"]]
    norm_cmd = [c for c in commands if c["reason"] not in ("E06_stale_test", "E06_wrong_run")]
    rtt = [c["ack"] - c["sent"] for c in norm_cmd if c["ack"] is not None]
    eff = [c["effect"] - c["decision_t"] for c in acc_cmd if c["effect"] is not None and c.get("effect_kind") == "edge"]
    n_switch = n_relay_switch
    res_mean = res_sum / max(1, res_n)
    res_sd = (max(0.0, res_sq / max(1, res_n) - res_mean ** 2)) ** 0.5
    e_twin = twin.e_dis_wh
    metrics = {
        "run_id": run_id, "scenario_id": sc.sid, "policy": policy_name, "repeat": repeat, "mode": mode, "seed": seed,
        "duration_h": dur / 3600, "stop_reason": stop_reason,
        "time_to_limit_h": dur / 3600, "right_censored": stop_reason == "completed",
        "soc_ref_start": soc_ref0, "min_soc_ref": float(min_soc_ref),
        "mae_soc_pp": float(np.mean(np.abs(err))), "rmse_soc_pp": float(np.sqrt(np.mean(err ** 2))),
        "max_soc_err_pp": float(np.max(np.abs(err))), "final_soc_err_pp": float(err[-1]),
        "ref_vs_true_mae_pp": float(np.mean(np.abs(terr))),
        "e_ref_dis_wh": acc["e_ref_dis"], "e_twin_dis_wh": e_twin,
        "energy_error_pct": 100 * abs(e_twin - acc["e_ref_dis"]) / acc["e_ref_dis"] if acc["e_ref_dis"] > 5 else float("nan"),
        "coverage_pct": 100 * acc["tel_valid"] / max(1, acc["tel_expected"]), "unknown_duration_s": acc["unknown_s"],
        "duplicates_dropped": acc["dups"], "transport": {"up": up.stats, "down": down.stats},
        "critical_unserved_wh": acc["e_crit_dem"] - acc["e_crit_srv"], "critical_served_wh": acc["e_crit_srv"],
        "aux_demand_wh": acc["e_aux_dem"], "aux_served_wh": acc["e_aux_srv"], "aux_unserved_wh": acc["e_aux_dem"] - acc["e_aux_srv"],
        "lolh_critical_h": acc["lolh_crit_h"], "lolh_total_h": acc["lolh_tot_h"],
        "lpsp_critical": (acc["e_crit_dem"] - acc["e_crit_srv"]) / max(acc["e_crit_dem"], 1e-9),
        "lpsp_total": (acc["e_crit_dem"] - acc["e_crit_srv"] + acc["e_aux_dem"] - acc["e_aux_srv"]) / max(acc["e_crit_dem"] + acc["e_aux_dem"], 1e-9),
        "e_gen_wh": acc["e_gen"], "e_curtailed_wh": acc["e_curt"],
        "service_checks": acc["svc_n"], "service_failures": acc["svc_fail"], "service_longest_fail_s": acc["svc_streak_max"],
        "availability_pct": 100 * (1 - acc["svc_fail"] / max(1, acc["svc_n"])),
        "commands": len(norm_cmd), "commands_accepted": len([c for c in norm_cmd if c["accepted"]]),
        "commands_effect_confirmed": len([c for c in norm_cmd if c["accepted"] and c["effect"] is not None]),
        "rtt": _lat_stats(rtt), "decision_to_effect": _lat_stats(eff),
        "switch_count": n_switch, "residual_w_mean": res_mean, "residual_w_sd": res_sd,
        "edge_log": [(float(a), b, c) for a, b, c in edge.log], "events": events,
        "commands_log": commands,
    }
    if keep_series:
        metrics["series"] = {kk: np.asarray(vv, dtype=float if kk != "pred_min" else object).tolist() for kk, vv in S.items()}
    return metrics


def build_bench(hw: dict, seed: int, calibrate: bool = True):
    """Create a bench unit, run E00 calibration of all channels and the E09
    capacity test; returns the instance and the calibration/capacity records."""
    from . import calibration, capacity
    from .battery import draw_truth

    rng = np.random.default_rng(seed)
    truth = draw_truth(hw, rng)
    chans = {name: make_channel(name, hw, rng) for name in ("M0", "M1", "M2", "M3", "M4", "M5", "REF")}
    cal = {}
    if calibrate:
        for name, chn in chans.items():
            cal[name] = calibration.run_calibration(chn, hw["channels"][name], hw["calibration_standard"], rng)
    temp = make_temp(hw, rng)
    cap = capacity.capacity_test(hw, truth, chans, rng)
    inst = BenchInstance(hw=hw, truth=truth, channels=chans, temp=temp, q_ref_ah=cap["q_ref_ah"], q_m1_ah=cap["q_m1_ah"],
                         eta_q_ref=cap["eta_q_ref"], eta_crit=float(rng.normal(hw["critical_branch"]["eta_mean"], hw["critical_branch"]["eta_sd"])),
                         eta_aux=float(rng.normal(hw["aux_branch"]["eta_mean"], hw["aux_branch"]["eta_sd"])), seed=seed)
    return inst, cal, cap


def math_isfinite(x):
    try:
        return math.isfinite(x)
    except TypeError:
        return False
