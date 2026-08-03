from sqlalchemy.orm import Session  # noqa: F401

from . import models, schemas  # noqa: F401

# Define your CRUD functions here, e.g.:
#
# def get_things(db: Session):
#     return db.query(models.Thing).all()
#
# def create_thing(db: Session, thing: schemas.ThingCreate):
#     db_thing = models.Thing(**thing.model_dump())
#     db.add(db_thing)
#     db.commit()
#     db.refresh(db_thing)
#     return db_thing
