# Optional camera geometry — retained candidate

The user selected DoorA (blue) for the original fixed camera. The candidate adds optional camera-level geometry and explicit object-source provenance; it does not change default overrides or inject video-specific outcomes.

Earlier checks actually ran: two camera-geometry tests and two override-guard tests passed; all40 cached organizer verdicts remained30/40 with zero false alarms. Fresh end-to-end inference after the changed calibration fingerprint was not run. No accuracy gain is claimed.

Do not promote before a fresh camera-calibration check: source changes invalidate the perception fingerprint, and the original-camera geometry must not be applied to mirrors or synthetic scenes. A23 used automatic/default calibration throughout. The patch includes the optional config and focused test source so the unpromoted work remains reviewable.
