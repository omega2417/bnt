# Security and privacy statement

Applies to release 2.0.0 of this deposit. It records what was checked before
publication, what the package deliberately does not contain, and what a reader
must not infer from it.

## 1. Automated audit performed before packaging

The whole package tree was scanned. Findings:

| Check | Result |
|---|---|
| IPv4 / IPv6 addresses | none found |
| MAC addresses | none found |
| Host names, domain names, internal node names | none found |
| E-mail addresses | none found in code, configuration or results |
| Credentials, passwords, API keys, tokens, private keys, certificates | none found |
| VPN or firewall configuration files | none present |
| CI/CD secrets, access logs, service logs | none present |
| Absolute local paths in shipped artifacts | none; byte-code caches were removed |
| Serial numbers, asset tags, procurement identifiers | none present |
| Personal data or third-party data | none present |

The scan can be repeated on the unpacked archive; the commands are listed in
`zenodo/upload_checklist.md`.

## 2. What the package contains instead of real infrastructure detail

The demonstration inventory describes an abstract two-site topology with generic
identifiers (`site_a`, `site_b`, link and device roles). Every value carries an
`evidence_status`, and none of them is `MEASURED` or `VENDOR_SPEC`. The topology
is therefore not a map of the real facility and cannot be used to plan an attack
against it.

## 3. Dual-use position

* Threats are modelled at **feature level only** — as changes to state variables
  and observable features. The package contains no exploit code, no payloads, no
  scanning or intrusion tooling, and no live or reachable targets.
* The package opens **no network sockets** and performs **no writes to any
  hardware**. External egress and hardware writes are refused by the safety
  policy, and the refusal is exercised by the automated safety tests.
* **HIL mode is blocked in software** while any critical parameter is weaker than
  `VENDOR_SPEC`. Four parameters are currently `UNKNOWN`, so HIL cannot start.
* The package is a planning and verification aid. It is **not a safety
  controller** and must never be placed in a control loop of a real power,
  network or protection system.

## 4. Personal data

No personal data is processed or published. The only personal information in the
deposit is the author metadata that the authors themselves publish for
attribution (name, ORCID, institutional affiliation).

## 5. Responsibilities remaining with the depositor before publication

These cannot be discharged by an automated scan and must be confirmed by the
corresponding author:

1. All co-authors have agreed to publication of the code, data and documentation.
2. Institutional and funder rights permit the licences in `LICENSES/`.
3. No content in this release is subject to an embargo, a restricted-access
   agreement, or a security classification.
4. Nothing in the demonstration inventory reveals a facility detail that the
   institution considers sensitive, even in abstracted form.

If any of the four cannot be confirmed, use Zenodo's restricted access or an
embargo and state the real reason and the access procedure in the record.

## 6. Reporting a problem

Report a suspected disclosure or a security concern to the corresponding author
listed in `README.md` and `CITATION.cff`. If the concern is confirmed, the fix is
published as a **new Zenodo version** with a note in `CHANGELOG.md`; published
files are not silently replaced.
