from dataclasses import dataclass
from typing import TypeGuard

from rdetoolkit.errors import RdeValidationError

MAX_TEMPLATE_LENGTH: int
MAX_EXPRESSIONS: int

def contains_expression(value: object) -> TypeGuard[str]: ...

class MagicExpressionError(RdeValidationError):
    offset: int
    reason: str
    def __init__(self, reason: str, offset: int) -> None: ...

@dataclass(frozen=True, slots=True)
class LiteralToken:
    text: str

@dataclass(frozen=True, slots=True)
class ExpressionToken:
    expression: str
    scope: str
    section: str
    key: str
    offset: int

def parse_template(template: str) -> tuple[LiteralToken | ExpressionToken, ...]: ...
