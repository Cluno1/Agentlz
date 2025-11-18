from typing import Any
from pydantic import BaseModel

class Result(BaseModel):
    success: bool = True
    code: int = 0
    message: str = "ok"
    data: Any = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "ok", code: int = 0) -> "Result":
        return cls(success=True, code=code, message=message, data=data)

    @classmethod
    def error(cls, message: str = "error", code: int = 1, data: Any = None) -> "Result":
        return cls(success=False, code=code, message=message, data=data)