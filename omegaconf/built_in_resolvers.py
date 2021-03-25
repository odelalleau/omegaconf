import os
import warnings

# from collections.abc import Mapping, MutableMapping
from typing import Any, Mapping, Optional, Union

from ._utils import _DEFAULT_MARKER_, _get_value, decode_primitive
from .base import Container
from .basecontainer import BaseContainer
from .dictconfig import DictConfig
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
    in_dict = _get_and_validate_dict_input(
        in_dict, root=_root_, resolver_name="oc.dict.keys"
    )
    assert isinstance(_parent_, BaseContainer)
    ret = OmegaConf.create(list(in_dict.keys()), parent=_parent_)
    assert isinstance(ret, ListConfig)
    return ret


def dict_values(
    in_dict: Union[str, Mapping[Any, Any]], _root_: BaseContainer, _parent_: Container
) -> ListConfig:
    in_dict = _get_and_validate_dict_input(
        in_dict, root=_root_, resolver_name="oc.dict.values"
    )
    assert isinstance(_parent_, BaseContainer)
    if isinstance(in_dict, DictConfig):
        # values = [v for _, v in in_dict.items_ex(resolve=False)]
        ret = OmegaConf.create(list(in_dict._content.values()), parent=_parent_)
        for node in ret._content:
            node._set_parent(in_dict)
        return ret
    else:
        values = list(in_dict.values())
    ret = OmegaConf.create(values, parent=_parent_)
    assert isinstance(ret, ListConfig)
    return ret


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


def _get_and_validate_dict_input(
    in_dict: Union[str, Mapping[Any, Any]],
    root: BaseContainer,
    resolver_name: str,
) -> Mapping[Any, Any]:
    if isinstance(in_dict, str):
        # Path to an existing key in the config: use `select()`.
        in_dict = OmegaConf.select(root, in_dict, throw_on_missing=True)

    if not isinstance(in_dict, Mapping):
        raise TypeError(
            f"`{resolver_name}` cannot be applied to objects of type: "
            f"{type(in_dict).__name__}"
        )

    return in_dict
