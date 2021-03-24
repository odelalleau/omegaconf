import os
import warnings

# from collections.abc import Mapping, MutableMapping
from typing import Any, Mapping, Optional, Union

from ._utils import _DEFAULT_MARKER_, _get_value, decode_primitive
from .base import Container
from .basecontainer import BaseContainer
from .errors import ValidationError
from .grammar_parser import parse
from .listconfig import ListConfig
from .omegaconf import OmegaConf


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


def dict_keys(
    in_dict: Union[str, Mapping[Any, Any]],
    _root_: BaseContainer,
    _parent_: Container,
) -> ListConfig:
    return _dict_impl(
        keys_or_values="keys", in_dict=in_dict, _root_=_root_, _parent_=_parent_
    )


def dict_values(
    in_dict: Union[str, Mapping[Any, Any]], _root_: BaseContainer, _parent_: Container
) -> ListConfig:
    return _dict_impl(
        keys_or_values="values", in_dict=in_dict, _root_=_root_, _parent_=_parent_
    )


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


def _dict_impl(
    keys_or_values: str,
    in_dict: Union[str, Mapping[Any, Any]],
    _root_: BaseContainer,
    _parent_: Container,
) -> ListConfig:
    if isinstance(in_dict, str):
        # Path to an existing key in the config: use `select()`.
        in_dict = OmegaConf.select(_root_, in_dict, throw_on_missing=True)

    if not isinstance(in_dict, Mapping):
        raise TypeError(
            f"`oc.dict.{keys_or_values}` cannot be applied to objects of type: "
            f"{type(in_dict).__name__}"
        )

    dict_method = getattr(in_dict, keys_or_values)
    assert isinstance(_parent_, BaseContainer)
    ret = OmegaConf.create(list(dict_method()), parent=_parent_)
    assert isinstance(ret, ListConfig)
    return ret
