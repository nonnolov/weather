"""One eligibility policy for discovery and the final pre-send check."""
from sqlalchemy import exists, select
from app.core.config import settings
from app.models.user import User
from app.models.location import Location
from app.models.line_subscription import LineSubscription
CONSENT_VERSION = "weather-alerts-v1"

def recipient_condition(*, legacy=None):
    if not settings.LINE_SUBSCRIPTIONS_ENABLED:
        return legacy if legacy is not None else User.external_id.startswith("U")
    return exists(select(LineSubscription.user_id).where(
        LineSubscription.user_id == User.external_id,
        LineSubscription.enabled.is_(True), LineSubscription.friend.is_(True),
        LineSubscription.consent_version == CONSENT_VERSION,
        LineSubscription.verified_location_id == User.current_location_id,
    ))

async def recipient_eligible(db, user_id: str, *, lock=False, expected_location_id=None) -> bool:
    if not settings.LINE_SUBSCRIPTIONS_ENABLED:
        return True  # Preserve the existing controlled deployment while the feature is off.
    query = select(User).where(User.external_id == user_id)
    if lock:
        query = query.with_for_update()
    user = await db.scalar(query)
    if user is None or user.current_location_id is None:
        return False
    if expected_location_id is not None and user.current_location_id != expected_location_id:
        return False
    sub_query = select(LineSubscription).where(LineSubscription.user_id == user_id)
    if lock:
        sub_query = sub_query.with_for_update()
    sub = await db.scalar(sub_query)
    location = await db.get(Location, user.current_location_id)
    return bool(sub and sub.enabled and sub.friend and sub.consent_version == CONSENT_VERSION
                and sub.verified_location_id == user.current_location_id and location and location.is_active)
