"""uavews - formation and preparation of the multisource sUAV early-warning dataset.

The package implements, as executable code, the data model and the technical
validation described in the Data Descriptor manuscript:

    events -> windows -> observations / media objects -> labels

Module map
----------
config        release parameters and controlled vocabularies
ids           stable, non-identifying identifiers and rotating pseudonyms
timebase      RFC 3339 <-> int64 UTC nanoseconds, clock offsets, Eq. (3)
geometry      warning-zone geometry, Eq. (1) boundary distance, Eq. (2) warning time
ingest.*      normalizers for source streams S1-S4
simulate      synthetic field-trial rehearsal corpus (NOT empirical data)
association   window construction and uncertainty-expanded association
labeling      evidence tiers, confidence, conflict adjudication
agreement     Krippendorff's alpha and temporal boundary agreement
validation    Eq. (4) completeness, Eq. (5) duplicate rate, sync, cross-modal, integrity
privacy       generalization, minimization, access tiering, residual-risk audit
splits        leakage-resistant evaluation manifests and their audit
trialdesign   field-trial sizing, warning-time budget, detectability curves
packaging     RO-Crate / DataCite / PROV-O package and SHA-256 manifest
viz           every figure used in the engineering report
cli           end-to-end driver
"""

__version__ = "0.1.0"

__all__ = [
    "config",
    "ids",
    "timebase",
    "geometry",
    "association",
    "labeling",
    "agreement",
    "validation",
    "privacy",
    "splits",
    "trialdesign",
    "packaging",
    "viz",
]
