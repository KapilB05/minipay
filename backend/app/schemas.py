from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    amount_paise: int
    status: str

    class Config:
        from_attributes = True
