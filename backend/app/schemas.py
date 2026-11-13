from pydantic import BaseModel, Field, EmailStr
from typing import Dict, List, Optional

class EnrollRequest(BaseModel):
    user_name: str = Field(..., min_length=2, max_length=100)
    user_email: str = Field(..., min_length=5, max_length=150)

class CompleteModuleRequest(BaseModel):
    user_email: str = Field(..., min_length=5, max_length=150)

class QuizSubmitRequest(BaseModel):
    user_name: str = Field(..., min_length=2, max_length=100)
    user_email: str = Field(..., min_length=5, max_length=150)
    answers: Dict[str, int] = Field(..., description="Mapping of question_id to selected option index")
