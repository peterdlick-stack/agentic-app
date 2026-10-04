# B independent review of C: PASS
Earlier in-progress observations were not acceptance. Author fixed malformed versions reason preservation and added production training evidence validation; final cases below supersede intermediate results.
No C code edited by reviewer. All fixtures synthetic; no human benefit asserted.
12 independent production pilot_metrics cases passed; process exit 0. Positive complete protocol accepted SYNTHETIC_TEST_PROTOCOL_SUPPORTED, false real_benefit_supported; low-benefit otherwise legal protocol rejected numerically with protocol_valid true.
[
  {
    "case": "legal synthetic positive",
    "status": "SYNTHETIC_TEST_PROTOCOL_SUPPORTED",
    "protocol_valid": true,
    "reasons": []
  },
  {
    "case": "non-dict versions",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "version_hashes_invalid",
      "training_feature_mismatch",
      "model_feature_mismatch",
      "registration_plan_mismatch",
      "cross_version_or_request",
      "row_chain_or_version_mismatch"
    ]
  },
  {
    "case": "missing evidence",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "evidence_bundle_missing"
    ]
  },
  {
    "case": "delete frozen session",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "trial_session_set_mismatch",
      "exposure_identity_invalid",
      "prediction_snapshot_exposure_time_chain",
      "future_feedback_or_time_chain",
      "source_orphan_or_unreferenced"
    ]
  },
  {
    "case": "forged variance",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "development_variance_mismatch",
      "registration_plan_mismatch"
    ]
  },
  {
    "case": "provenance-only promotion",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "source_kind_mismatch",
      "training_bundle_session_mismatch",
      "training_label_provenance_mismatch",
      "p2_training_ineligible",
      "p2_model_untrained_or_provenance",
      "registration_plan_mismatch",
      "row_chain_or_version_mismatch"
    ]
  },
  {
    "case": "duplicate training exposure new event id",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "training_bundle_invalid:duplicate_feedback",
      "training_bundle_label_set_mismatch",
      "training_bundle_label_mismatch",
      "model_training_binding_mismatch"
    ]
  },
  {
    "case": "distinct session ids same independent unit",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "trial_sessions_not_independent"
    ]
  },
  {
    "case": "legal zero benefit",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": true,
    "reasons": [
      "gain_at_least_10pp",
      "gain_lower_positive",
      "worst_missing_lower_positive"
    ]
  },
  {
    "case": "forged N",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "planned_session_ids_invalid",
      "schedule_not_frozen_balanced_order",
      "sample_size_not_recomputed",
      "registration_plan_mismatch",
      "trial_session_set_mismatch",
      "fixed_sample_size"
    ]
  },
  {
    "case": "P2 actual fallback",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "exposure_source_mismatch",
      "policy_not_delivered",
      "prediction_exposure_mismatch",
      "row_chain_or_version_mismatch"
    ]
  },
  {
    "case": "future feedback",
    "status": "NO_USER_BENEFIT_EVIDENCE",
    "protocol_valid": false,
    "reasons": [
      "feedback_source_mismatch",
      "future_feedback_or_time_chain",
      "prediction_update_chain_mismatch"
    ]
  }
]
metrics SHA256 156c73b041c548611d7bcef86bb486e15e5e2e4d74e35877a147d2a5fc089a20
