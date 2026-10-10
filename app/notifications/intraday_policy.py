"""Explicit policy selection; v1 remains the default in every runtime caller."""
from app.notifications.intraday_comparison import POLICY_VERSION, compare_intraday
from app.notifications.intraday_candidate_policy import CANDIDATE_POLICY_VERSION, compare_candidate_policy

SUPPORTED_POLICIES = (POLICY_VERSION, CANDIDATE_POLICY_VERSION)


def comparator_for(policy_version):
    if policy_version == POLICY_VERSION:
        return compare_intraday
    if policy_version == CANDIDATE_POLICY_VERSION:
        return compare_candidate_policy
    raise ValueError("Unsupported intraday policy")


def delivery_prefix(policy_version, location_id):
    comparator_for(policy_version)
    version = "v1" if policy_version == POLICY_VERSION else "v2"
    return f"rain-intraday:{version}:{location_id}:"
