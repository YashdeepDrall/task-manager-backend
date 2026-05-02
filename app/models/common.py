from typing import Any

from bson import ObjectId
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.str_schema(),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, value: ObjectId | str) -> ObjectId:
        if isinstance(value, ObjectId):
            return value

        if ObjectId.is_valid(value):
            return ObjectId(value)

        raise ValueError("Invalid ObjectId")


def object_id_or_400(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return ObjectId(value)


def stringify_object_id(document: dict[str, Any]) -> dict[str, Any]:
    data = dict(document)
    if "_id" in data:
        data["id"] = str(data.pop("_id"))
    return data
