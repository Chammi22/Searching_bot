"""Pydantic schemas for vacancy data validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VacancySchema(BaseModel):
    """Schema for vacancy data validation."""

    external_id: str = Field(..., description="Unique ID from source website")
    source: str = Field(..., description="Source website (gsz.gov.by, praca.by, etc.)")
    date_posted: Optional[datetime] = Field(None, description="Date when vacancy was posted")
    company_name: str = Field(..., min_length=1, description="Company name")
    company_address: Optional[str] = Field(None, description="Company address")
    position: str = Field(..., min_length=1, description="Job position/specialty")
    vacancies_count: Optional[int] = Field(None, ge=0, description="Number of available positions")
    salary: Optional[str] = Field(None, description="Salary information")
    contact_person: Optional[str] = Field(None, description="Contact person name")
    contact_phone: Optional[str] = Field(None, description="Contact phone number")
    url: Optional[str] = Field(None, description="URL to vacancy page")

    @field_validator("external_id", "source", "company_name", "position")
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        """Validate required string fields."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "external_id": "12345",
                "source": "gsz.gov.by",
                "date_posted": "2024-01-15T10:00:00",
                "company_name": "ООО «Тиктри»",
                "company_address": "г. Минск, ул. Примерная, 1",
                "position": "подсобный рабочий",
                "vacancies_count": 5,
                "salary": "500-700 BYN",
                "contact_person": "Иванов Иван Иванович",
                "contact_phone": "+375 29 123-45-67",
                "url": "https://gsz.gov.by/directory/vacancy/12345",
            }
        }
