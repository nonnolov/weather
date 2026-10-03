from pydantic import BaseModel

from app.schemas.location import LocationRead


class UserLocationRead(BaseModel):
    external_user_id: str
    location: LocationRead
