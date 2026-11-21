from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(..., min_length=2, max_length=200)
    password: str = Field(..., min_length=8, max_length=72)
    cnic: str | None = Field(None, pattern=r"^\d{5}-\d{7}-\d$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    cnic: str | None
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"