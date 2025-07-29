from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
from pathlib import Path


class FieldType(Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    TAGS = "tags"


@dataclass
class MetadataField:
    name: str
    display_name: str
    field_type: FieldType
    required: bool = False
    default_value: Optional[Any] = None
    options: Optional[List[str]] = None  # For SELECT/MULTISELECT types
    description: Optional[str] = None
    validation_pattern: Optional[str] = None  # Regex pattern for validation
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "field_type": self.field_type.value,
            "required": self.required,
            "default_value": self.default_value,
            "options": self.options,
            "description": self.description,
            "validation_pattern": self.validation_pattern
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetadataField':
        return cls(
            name=data["name"],
            display_name=data["display_name"],
            field_type=FieldType(data["field_type"]),
            required=data.get("required", False),
            default_value=data.get("default_value"),
            options=data.get("options"),
            description=data.get("description"),
            validation_pattern=data.get("validation_pattern")
        )


@dataclass
class Profile:
    id: str
    name: str
    description: str
    fields: List[MetadataField] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def add_field(self, field: MetadataField):
        if any(f.name == field.name for f in self.fields):
            raise ValueError(f"Field with name '{field.name}' already exists")
        self.fields.append(field)
    
    def remove_field(self, field_name: str):
        self.fields = [f for f in self.fields if f.name != field_name]
    
    def get_field(self, field_name: str) -> Optional[MetadataField]:
        return next((f for f in self.fields if f.name == field_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Profile':
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            fields=[MetadataField.from_dict(f) for f in data.get("fields", [])],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )
    
    def save_to_file(self, path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, path: Path) -> 'Profile':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))