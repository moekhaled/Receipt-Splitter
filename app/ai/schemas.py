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

# ✅ IMPORTANT: RootModel wrapper so we can generate JSON schema + validate
class AIAction(RootModel[Union[CreateSessionAction, GeneralInquiryAction, EditSessionAction]]):
    pass