# Software versions

## Analysis environment

Recorded from the environment in which the figures and tables in this release
were produced.

| Component | Version |
|---|---|
| Python | 3.11.15 |
| NumPy | 2.4.6 |
| pandas | 3.0.5 |
| SciPy | 1.17.1 |
| Matplotlib | 3.11.1 |
| PyYAML | 6.0.2 |

Regenerate with `python -c "import numpy,pandas,scipy,matplotlib;print(...)"` or
`pip freeze > environment/pip-freeze.txt`.

## Testbed stack (manuscript Table 2)

| Tier | Component | Version |
|---|---|---|
| IoT segment | Eclipse Mosquitto | 2.0.18 |
| IoT segment | MQTT protocol | 5.0 over TLS 1.3 |
| Edge cluster | Raspberry Pi OS (64-bit) | 2025-05-13 |
| Edge cluster | K3s | v1.30.2+k3s1 |
| Edge cluster | Suricata | 7.0.5 |
| Edge cluster | containerd | 1.7.18 |
| Cloud tier | Kubernetes | v1.30.2 |
| Cloud tier | Ubuntu Server | 24.04.2 LTS |
| Digital-twin core | Eclipse Ditto | 3.5.6 |
| Monitoring | Prometheus | 2.53.0 |
| Monitoring | Grafana | 11.1.0 |
| Attacker host | Kali Linux | 2025.2 |
| Attacker host | hping3 | 3.0.0-alpha-2 |
| Attacker host | nmap | 7.95 |

> The Raspberry Pi 5 boards, the three cloud VMs (8 vCPU / 16 GB each) and the
> single attacker host are as described in manuscript Table 2. Twelve sensors are
> **emulated**, not physical — see the naming note in
> `manuscript_integration/02_methods.md`.

## Container digests

`container_digests.txt` must be regenerated from the real campaign with:

    kubectl get pods -A -o jsonpath='{range .items[*].status.containerStatuses[*]}{.imageID}{"\n"}{end}' | sort -u
