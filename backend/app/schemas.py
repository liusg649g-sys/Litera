from datetime import timezone
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)

class RegisterInput(InputModel):
    email: EmailStr = Field(max_length=254)
    password: SecretStr
    display_name: str = Field(alias="displayName", min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def trim_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("显示名称不能为空")
        return value

class LoginInput(InputModel):
    email: EmailStr = Field(max_length=254)
    password: SecretStr

class ProfileInput(InputModel):
    display_name: str = Field(alias="displayName", min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def trim_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("显示名称不能为空")
        return value

def user_dto(user):
    return {
        "id": user.id, "email": user.email, "displayName": user.display_name,
        "createdAt": user.created_at.replace(tzinfo=timezone.utc).isoformat(),
    }
