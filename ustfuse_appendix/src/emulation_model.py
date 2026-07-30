"""Documented baseline-emulation model (extends FuseMetrics Lab v1 kBaselines).
PROVISIONAL: multipliers on axes S3 v1 does not reimplement independently.
f1/mota/ece/idsw multipliers reproduce the released tool exactly; the remaining
axes (pd/far/brier/idf1/frag/rmse) are a documented extension, all relative to
UST-Fuse=1.0. These characterize capability profiles, NOT independent runs, and
must be replaced by real B1-B6 implementations before publication (task section 7).
B4 and B7 are NOT emulated here: they come from genuine S2 component toggles."""
# axis: pd,far,f1,brier,ece (detection/classification) ; mota,idf1,frag,idsw,rmse (tracking)
BASELINES_EMULATED = {
 'B1 - CNN on Doppler [9]':      dict(pd=0.93, far=1.60, f1=0.88, brier=1.70, ece=1.90, mota=0.72, idf1=0.74, frag=2.50, idsw=3.0, rmse=1.60),
 'B2 - LSTM sequence [15]':      dict(pd=0.95, far=1.40, f1=0.95, brier=1.40, ece=1.55, mota=0.80, idf1=0.82, frag=2.00, idsw=2.2, rmse=1.45),
 'B3 - Kalman + NN [42]':        dict(pd=0.90, far=1.90, f1=0.70, brier=2.20, ece=2.60, mota=0.85, idf1=0.78, frag=2.30, idsw=2.4, rmse=1.70),
 'B5 - SORT [36]':               dict(pd=0.92, far=1.70, f1=0.72, brier=2.00, ece=2.40, mota=0.88, idf1=0.80, frag=2.00, idsw=2.1, rmse=1.50),
 'B6 - DeepSORT [37]':           dict(pd=0.97, far=1.20, f1=0.96, brier=1.25, ece=1.45, mota=0.90, idf1=0.90, frag=1.50, idsw=1.6, rmse=1.15),
}
def emulate(ref, mult):
    """ref: dict of UST-Fuse point values; mult: per-axis multipliers."""
    return {k: ref[k]*mult[k] for k in mult}
