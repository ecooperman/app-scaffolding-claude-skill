from pydantic import BaseModel, ConfigDict  # noqa: F401

# Define your Pydantic schemas here, following the Base/Create/Update/read
# pattern, e.g.:
#
# class ThingBase(BaseModel):
#     name: str
#
# class ThingCreate(ThingBase):
#     pass
#
# class ThingUpdate(BaseModel):
#     name: Optional[str] = None
#
# class Thing(ThingBase):
#     model_config = ConfigDict(from_attributes=True)
#     id: int
