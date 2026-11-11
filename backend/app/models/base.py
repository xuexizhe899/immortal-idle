"""完整响应字段在输出 schema 中必填，输入仍可省略有默认值的字段。"""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
