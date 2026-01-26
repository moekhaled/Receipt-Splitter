from enum import Enum


class Intent(str, Enum):
    GENERAL_INQUIRY = "general_inquiry"
    CREATE_SESSION = "create_session"
    EDIT_SESSION = "edit_session"
    EDIT_SESSION_ENTITIES = "edit_session_entities"
    EDIT_PERSON = "edit_person"
    EDIT_ITEM = "edit_item"
