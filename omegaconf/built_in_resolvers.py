import os
import warnings
from typing import Any, Dict, List, Optional

from ._utils import _DEFAULT_MARKER_, _get_value, decode_primitive
from .base import Container
from .errors import ValidationError
from .grammar_parser import parse


def decode(expr: Optional[str], _parent_: Container) -> Any:
    """
    Parse and evaluate `expr` according to the `singleElement` rule of the grammar.

    If `expr` is `None`, then return `None`.
    """
    if expr is None:
        return None

    if not isinstance(expr, str):
        raise TypeError(
            f"`oc.decode` can only take strings or None as input, "
            f"but `{expr}` is of type {type(expr).__name__}"
        )

    parse_tree = parse(expr, parser_rule="singleElement", lexer_mode="VALUE_MODE")
    val = _parent_.resolve_parse_tree(parse_tree)
    return _get_value(val)


def dict_keys(in_dict: Dict[Any, Any]) -> List[Any]:
    return list(in_dict.keys())


def dict_values(in_dict: Dict[Any, Any]) -> List[Any]:
    return list(in_dict.values())


def env(key: str, default: Optional[str] = _DEFAULT_MARKER_) -> Optional[str]:
    if (
        default is not _DEFAULT_MARKER_
        and default is not None
        and not isinstance(default, str)
    ):
        raise TypeError(
            f"The default value of the `oc.env` resolver must be a string or "
            f"None, but `{default}` is of type {type(default).__name__}"
        )

    try:
        return os.environ[key]
    except KeyError:
        if default is not _DEFAULT_MARKER_:
            return default
        else:
            raise KeyError(f"Environment variable '{key}' not found")


# DEPRECATED: remove in 2.2
def legacy_env(key: str, default: Optional[str] = None) -> Any:
    warnings.warn(
        "The `env` resolver is deprecated, see https://github.com/omry/omegaconf/issues/573",
    )

    try:
        return decode_primitive(os.environ[key])
    except KeyError:
        if default is not None:
            return decode_primitive(default)
        else:
            raise ValidationError(f"Environment variable '{key}' not found")
