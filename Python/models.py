from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class HelpdeskKBItemBase(SQLModel):
    title: str = Field(max_length=100)
    question: str
    answer: str
    votes: int = Field(default=0)
    recommendations: int = Field(default=0)
    last_updated: datetime
    category_id: int
    enabled: bool = Field(default=True)
    team_id: Optional[int] = None
    order: Optional[int] = None

class HelpdeskKBItem(HelpdeskKBItemBase, table=True):
    __tablename__ = "helpdesk_kbitem"
    id: Optional[int] = Field(default=None, primary_key=True)


class HelpdeskKBItemCreate(HelpdeskKBItemBase):
    pass

class HelpdeskKBItemRead(HelpdeskKBItemBase):
    id: int 
    
class HelpdeskKBCategoryBase(SQLModel):
    title: str = Field(max_length=100)
    slug: str = Field(max_length=50)
    description: str
    queue_id: int
    public: bool
    name: str = Field(max_length=100)
    
class HelpdeskKBCategory(HelpdeskKBCategoryBase, table=True):
    __tablename__ = "helpdesk_kbcategory"
    id: Optional[int] = Field(default=None, primary_key=True)


class HelpdeskKBCategoryCreate(HelpdeskKBItemBase):
    pass

class HelpdeskKBCategoryRead(HelpdeskKBItemBase):
    id: int 