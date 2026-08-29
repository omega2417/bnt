"""Normalizers that turn raw source deliveries into canonical records.

One adapter per source family. Each adapter is responsible for exactly three
things and nothing else:

* parsing the delivery format the source actually uses,
* emitting the minimum event envelope every stream must produce
  (source_id, source_event_id_hash, UTC interval, clock quality, generalized
  cell, modality, payload reference, checksum, rights status, provenance),
* recording what it could not determine, with a reason code.

Association, labelling, quality scoring, and privacy transformation happen
downstream. Keeping them out of the adapters is what allows a new source family
to be added without touching the validation gates.
"""

from . import s1_takeoff, s2_public_warning, s3_mobile, s4_media  # noqa: F401
