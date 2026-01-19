from pydantic import BaseModel, Field, RootModel
from typing import List, Literal, Union, Optional

class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    quantity: int = Field(ge=1, default=1)

class PersonIn(BaseModel):
    name: str = Field(min_length=1)
    items: List[ItemIn] = Field(default_factory=list)

class SessionIn(BaseModel):
    title: str = Field(min_length=1)
    vat: float = Field(ge=0, le=100, default=0)
    service: float = Field(ge=0, le=100, default=0)
    discount: float = Field(ge=0, le=100, default=0)

class CreateSessionAction(BaseModel):
    intent: Literal["create_session"]
    session: SessionIn
    people: List[PersonIn] = Field(min_length=1)

class GeneralInquiryAction(BaseModel):
    intent: Literal["general_inquiry"]
    answer: str = Field(min_length=1)

class EditSessionFields(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    vat: Optional[float] = Field(default=None, ge=0, le=100)     # AI uses vat (DB uses tax)
    service: Optional[float] = Field(default=None, ge=0, le=100)
    discount: Optional[float] = Field(default=None, ge=0, le=100)

class EditSessionAction(BaseModel):
    intent: Literal["edit_session"]
    # If user is already inside a session page, frontend provides this context.
    session_id: Optional[int] = None
    # Fallback if no session_id is provided (user typed a name)
    session_query: Optional[str] = None
    updates: EditSessionFields
class EditPersonAction(BaseModel):
    intent: Literal["edit_person"]

    # frontend/server context
    session_id: Optional[int] = None

    operation: Literal["add", "rename", "delete"]

    # required for rename/delete
    person_id: Optional[int] = Field(default=None, gt=0)

    # required for add/rename
    new_name: Optional[str] = Field(default=None, min_length=1)
    ref: Optional[str] = Field(default=None, min_length=1, max_length=32)

class EditItemUpdates(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, ge=1)

class EditItemAction(BaseModel):
    intent: Literal["edit_item"]

    # provided by frontend context or inferred by model from context JSON
    session_id: Optional[int] = None

    operation: Literal["add", "update", "delete", "move"]

    # for update/delete/move
    item_id: Optional[int] = None

    # for add/move
    to_person_id: Optional[int] = None
    #Temp ref pointing to a person created earlier in same batch
    to_person_ref: Optional[str] = Field(default=None, min_length=1, max_length=32)
    # for add
    name: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = Field(default=None, ge=1)

    # for update
    updates: Optional[EditItemUpdates] = None
OperationAction = Union[EditPersonAction, EditItemAction]

class EditSessionEntitiesAction(BaseModel):
    intent: Literal["edit_session_entities"]
    session_id: Optional[int] = None
    operations: List[OperationAction] = Field(default_factory=list, min_length=1)


# ✅ IMPORTANT: RootModel wrapper so we can generate JSON schema + validate
class AIAction(RootModel[Union[CreateSessionAction, GeneralInquiryAction, EditSessionAction,EditPersonAction, EditItemAction,EditSessionEntitiesAction]]):
    pass