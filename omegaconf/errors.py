from typing import Any, Optional, Type


class OmegaConfBaseException(Exception):
    # would ideally be typed Optional[Node]
    parent_node: Any
    child_node: Any
    key: Any
    full_key: Optional[str]
    value: Any
    msg: Optional[str]
    cause: Optional[Exception]
    object_type: Optional[Type[Any]]
    object_type_str: Optional[str]
    ref_type: Optional[Type[Any]]
    ref_type_str: Optional[str]

    _initialized: bool = False

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.parent_node = None
        self.child_node = None
        self.key = None
        self.full_key = None
        self.value = None
        self.msg = None
        self.object_type = None
        self.ref_type = None


class MissingMandatoryValue(OmegaConfBaseException):
    """Thrown when a variable flagged with '???' value is accessed to
    indicate that the value was not set"""


class UnsupportedValueType(OmegaConfBaseException, ValueError):
    """
    Thrown when an input value is not of supported type
    """


class KeyValidationError(OmegaConfBaseException, ValueError):
    """
    Thrown when an a key of invalid type is used
    """


class ValidationError(OmegaConfBaseException, ValueError):
    """
    Thrown when a value fails validation
    """


class ReadonlyConfigError(OmegaConfBaseException):
    """
    Thrown when someone tries to modify a frozen config
    """


class UnsupportedInterpolationType(OmegaConfBaseException, ValueError):
    """
    Thrown when an attempt to use an unregistered interpolation is made
    """


class ConfigKeyError(OmegaConfBaseException, KeyError):
    """
    Thrown from DictConfig when a regular dict access would have caused a KeyError.
    """

    msg: str

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg

    def __str__(self) -> str:
        """
        Workaround to nasty KeyError quirk: https://bugs.python.org/issue2651
        """
        return self.msg


class ConfigAttributeError(OmegaConfBaseException, AttributeError):
    """
    Thrown from a config object when a regular access would have caused an AttributeError.
    """


class ConfigTypeError(OmegaConfBaseException, TypeError):
    """
    Thrown from a config object when a regular access would have caused a TypeError.
    """


class ConfigIndexError(OmegaConfBaseException, IndexError):
    """
    Thrown from a config object when a regular access would have caused an IndexError.
    """


class ConfigValueError(OmegaConfBaseException, ValueError):
    """
    Thrown from a config object when a regular access would have caused a ValueError.
    """


class InterpolationParseError(OmegaConfBaseException):
    """
    Base class for interpolation parsing errors.
    """


class InterpolationSyntaxError(InterpolationParseError):
    """
    Thrown when a syntax error is detected while parsing an interpolation.
    """


class InterpolationTypeError(InterpolationParseError):
    """
    Thrown when there is a type mismatch during parsing of an interpolation.
    """


class InterpolationAmbiguityError(InterpolationParseError):
    """
    From ANTLR only.
    """


class InterpolationAttemptingFullContextError(InterpolationParseError):
    """
    From ANTLR only.
    """


class InterpolationContextSensitivityError(InterpolationParseError):
    """
    From ANTLR only.
    """
