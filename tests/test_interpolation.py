import math
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import pytest

from omegaconf import (
    DictConfig,
    IntegerNode,
    ListConfig,
    OmegaConf,
    Resolver,
    ValidationError,
)
from omegaconf.errors import (
    ConfigKeyError,
    InterpolationSyntaxError,
    InterpolationTypeError,
    UnsupportedInterpolationType,
)


def test_str_interpolation_dict_1() -> None:
    # Simplest str_interpolation
    c = OmegaConf.create(dict(a="${referenced}", referenced="bar"))
    assert c.referenced == "bar"
    assert c.a == "bar"


def test_str_interpolation_key_error_1() -> None:
    # Test that a KeyError is thrown if an str_interpolation key is not available
    c = OmegaConf.create(dict(a="${not_found}"))

    with pytest.raises(KeyError):
        _ = c.a


def test_str_interpolation_key_error_2() -> None:
    # Test that a KeyError is thrown if an str_interpolation key is not available
    c = OmegaConf.create(dict(a="${not.found}"))

    with pytest.raises(KeyError):
        c.a


def test_str_interpolation_3() -> None:
    # Test that str_interpolation works with complex strings
    c = OmegaConf.create(dict(a="the year ${year}", year="of the cat"))

    assert c.a == "the year of the cat"


def test_str_interpolation_4() -> None:
    # Test that a string with multiple str_interpolations works
    c = OmegaConf.create(
        dict(a="${ha} ${ha} ${ha}, said Pennywise, ${ha} ${ha}... ${ha}!", ha="HA")
    )

    assert c.a == "HA HA HA, said Pennywise, HA HA... HA!"


def test_deep_str_interpolation_1() -> None:
    # Test deep str_interpolation works
    c = OmegaConf.create(
        dict(
            a="the answer to the universe and everything is ${nested.value}",
            nested=dict(value=42),
        )
    )

    assert c.a == "the answer to the universe and everything is 42"


def test_deep_str_interpolation_2() -> None:
    # Test that str_interpolation of a key that is nested works
    c = OmegaConf.create(
        dict(
            out=42,
            deep=dict(inside="the answer to the universe and everything is ${out}"),
        )
    )

    assert c.deep.inside == "the answer to the universe and everything is 42"


def test_simple_str_interpolation_inherit_type() -> None:
    # Test that str_interpolation of a key that is nested works
    c = OmegaConf.create(
        dict(
            inter1="${answer1}",
            inter2="${answer2}",
            inter3="${answer3}",
            inter4="${answer4}",
            answer1=42,
            answer2=42.0,
            answer3=False,
            answer4="string",
        )
    )

    assert type(c.inter1) == int
    assert type(c.inter2) == float
    assert type(c.inter3) == bool
    assert type(c.inter4) == str


def test_complex_str_interpolation_is_always_str_1() -> None:
    c = OmegaConf.create(dict(two=2, four=4, inter1="${four}${two}", inter2="4${two}"))

    assert type(c.inter1) == str
    assert c.inter1 == "42"
    assert type(c.inter2) == str
    assert c.inter2 == "42"


@pytest.mark.parametrize(  # type: ignore
    "input_,key,expected",
    [
        (dict(a=10, b="${a}"), "b", 10),
        (dict(a=10, b=[1, "${a}", 3, 4]), "b.1", 10),
        (dict(a="${b.1}", b=[1, dict(c=10), 3, 4]), "a", dict(c=10)),
        (dict(a="${b}", b=[1, 2]), "a", [1, 2]),
        (dict(a="foo-${b}", b=[1, 2]), "a", "foo-[1, 2]"),
        (dict(a="foo-${b}", b=dict(c=10)), "a", "foo-{'c': 10}"),
    ],
)
def test_interpolation(input_: Dict[str, Any], key: str, expected: str) -> None:
    c = OmegaConf.create(input_)
    assert OmegaConf.select(c, key) == expected


def test_2_step_interpolation() -> None:
    c = OmegaConf.create(dict(src="bar", copy_src="${src}", copy_copy="${copy_src}"))
    assert c.copy_src == "bar"
    assert c.copy_copy == "bar"


def test_env_interpolation1() -> None:
    try:
        os.environ["foobar"] = "1234"
        c = OmegaConf.create({"path": "/test/${env:foobar}"})
        assert c.path == "/test/1234"
    finally:
        del os.environ["foobar"]


def test_env_interpolation_not_found() -> None:
    c = OmegaConf.create({"path": "/test/${env:foobar}"})
    with pytest.raises(
        ValidationError, match=re.escape("Environment variable 'foobar' not found")
    ):
        c.path


def test_env_default_str_interpolation_missing_env() -> None:
    if os.getenv("foobar") is not None:
        del os.environ["foobar"]
    c = OmegaConf.create({"path": "/test/${env:foobar,abc}"})
    assert c.path == "/test/abc"


def test_env_default_interpolation_missing_env_default_with_slash() -> None:
    if os.getenv("foobar") is not None:
        del os.environ["foobar"]
    c = OmegaConf.create({"path": "${env:DATA_PATH,a/b}"})
    assert c.path == "a/b"


def test_env_default_interpolation_env_exist() -> None:
    os.environ["foobar"] = "1234"
    c = OmegaConf.create({"path": "/test/${env:foobar,abc}"})
    assert c.path == "/test/1234"


@pytest.mark.parametrize(  # type: ignore
    "value,expected",
    [
        # bool
        ("false", False),
        ("true", True),
        # int
        ("10", 10),
        ("-10", -10),
        # float
        ("10.0", 10.0),
        ("-10.0", -10.0),
        # strings
        ("off", "off"),
        ("no", "no"),
        ("on", "on"),
        ("yes", "yes"),
        (">1234", ">1234"),
        (":1234", ":1234"),
        ("/1234", "/1234"),
        # yaml strings are not getting parsed by the env resolver
        ("foo: bar", "foo: bar"),
        ("foo: \n - bar\n - baz", "foo: \n - bar\n - baz"),
    ],
)
def test_env_values_are_typed(value: Any, expected: Any) -> None:
    try:
        os.environ["my_key"] = value
        c = OmegaConf.create(dict(my_key="${env:my_key}"))
        assert c.my_key == expected
    finally:
        del os.environ["my_key"]


def test_register_resolver_twice_error(restore_resolvers: Any) -> None:
    def foo() -> int:
        return 10

    OmegaConf.register_resolver("foo", foo)
    with pytest.raises(AssertionError):
        OmegaConf.register_resolver("foo", lambda: 10)


def test_clear_resolvers(restore_resolvers: Any) -> None:
    assert OmegaConf.get_resolver("foo") is None
    OmegaConf.register_resolver("foo", lambda x: int(x) + 10)
    assert OmegaConf.get_resolver("foo") is not None
    OmegaConf.clear_resolvers()
    assert OmegaConf.get_resolver("foo") is None


def test_register_resolver_1(restore_resolvers: Any) -> None:
    OmegaConf.register_resolver("plus_10", lambda x: x + 10, variables_as_strings=False)
    c = OmegaConf.create(dict(k="${plus_10:990}"))

    assert type(c.k) == int
    assert c.k == 1000


def test_resolver_cache_1(restore_resolvers: Any) -> None:
    # resolvers are always converted to stateless idempotent functions
    # subsequent calls to the same function with the same argument will always return the same value.
    # this is important to allow embedding of functions like time() without having the value change during
    # the program execution.
    OmegaConf.register_resolver("random", lambda _: random.randint(0, 10000000))
    c = OmegaConf.create(dict(k="${random:_}"))
    assert c.k == c.k


def test_resolver_cache_2(restore_resolvers: Any) -> None:
    """
    Tests that resolver cache is not shared between different OmegaConf objects
    """
    OmegaConf.register_resolver("random", lambda _: random.randint(0, 10000000))
    c1 = OmegaConf.create(dict(k="${random:_}"))
    c2 = OmegaConf.create(dict(k="${random:_}"))
    assert c1.k != c2.k
    assert c1.k == c1.k
    assert c2.k == c2.k


def test_resolver_cache_3_dict_list(restore_resolvers: Any) -> None:
    """
    Tests that the resolver cache works as expected with lists and dicts.
    """
    OmegaConf.register_resolver(
        "random", lambda _: random.uniform(0, 1), variables_as_strings=False
    )
    c = OmegaConf.create(
        dict(
            lst1="${random:[0, 1]}",
            lst2="${random:[0, 1]}",
            lst3="${random:[]}",
            dct1="${random:{0: 1, 1: 2}}",
            dct2="${random:{1: 2, 0: 1}}",
            mixed1="${random:{0: [1.1], 1: {a: true, b: false, c: null, d: []}}}",
            mixed2="${random:{0: [1.1], 1: {b: false, c: null, a: true, d: []}}}",
        )
    )
    assert c.lst1 == c.lst1
    assert c.lst1 == c.lst2
    assert c.lst1 != c.lst3
    assert c.dct1 == c.dct1
    assert c.dct1 != c.dct2
    assert c.mixed1 == c.mixed1
    assert c.mixed2 == c.mixed2
    assert c.mixed1 != c.mixed2


@pytest.mark.parametrize(  # type: ignore
    "resolver,name,key,result",
    [
        (lambda *args: args, "arg_list", "${my_resolver:cat, dog}", ("cat", "dog")),
        (
            lambda *args: args,
            "escape_comma",
            "${my_resolver:cat\\, do g}",
            ("cat, do g",),
        ),
        (
            lambda *args: args,
            "escape_whitespace",
            "${my_resolver:cat\\, do g}",
            ("cat, do g",),
        ),
        (lambda: "zero", "zero_arg", "${my_resolver:}", "zero"),
    ],
)
def test_resolver_that_allows_a_list_of_arguments(
    restore_resolvers: Any, resolver: Resolver, name: str, key: str, result: Any
) -> None:
    OmegaConf.register_resolver("my_resolver", resolver)
    c = OmegaConf.create({name: key})
    assert isinstance(c, DictConfig)
    assert c[name] == result


def test_resolver_deprecated_behavior(restore_resolvers: Any) -> None:
    OmegaConf.register_resolver("my_resolver", lambda *args: args)
    c = OmegaConf.create(
        {
            "int": "${my_resolver:1}",
            "null": "${my_resolver:null}",
            "bool": "${my_resolver:TruE,falSE}",
            "str": "${my_resolver:a,b,c}",
        }
    )
    with pytest.warns(UserWarning):
        assert c.int == ("1",)
    with pytest.warns(UserWarning):
        assert c.null == ("null",)
    with pytest.warns(UserWarning):
        assert c.bool == ("TruE", "falSE")
    assert c.str == ("a", "b", "c")


def test_copy_cache(restore_resolvers: Any) -> None:
    OmegaConf.register_resolver("random", lambda _: random.randint(0, 10000000))
    d = {"k": "${random:_}"}
    c1 = OmegaConf.create(d)
    assert c1.k == c1.k

    c2 = OmegaConf.create(d)
    assert c2.k != c1.k
    OmegaConf.set_cache(c2, OmegaConf.get_cache(c1))
    assert c2.k == c1.k

    c3 = OmegaConf.create(d)

    assert c3.k != c1.k
    OmegaConf.copy_cache(c1, c3)
    assert c3.k == c1.k


def test_clear_cache(restore_resolvers: Any) -> None:
    OmegaConf.register_resolver("random", lambda _: random.randint(0, 10000000))
    c = OmegaConf.create(dict(k="${random:_}"))
    old = c.k
    OmegaConf.clear_cache(c)
    assert old != c.k


def test_supported_chars() -> None:
    supported_chars = "abc123`~!@#$%^&*()-_=+\\|;.<>/?"
    c = OmegaConf.create(dict(dir1="${copy:" + supported_chars + "}"))

    OmegaConf.register_resolver("copy", lambda x: x)
    assert c.dir1 == supported_chars


def test_interpolation_in_list_key_error() -> None:
    # Test that a KeyError is thrown if an str_interpolation key is not available
    c = OmegaConf.create(["${10}"])
    assert isinstance(c, ListConfig)

    with pytest.raises(KeyError):
        c[0]


def test_unsupported_interpolation_type() -> None:
    c = OmegaConf.create(dict(foo="${wrong_type:ref}"))

    with pytest.raises(ValueError):
        c.foo


def test_incremental_dict_with_interpolation() -> None:
    conf = OmegaConf.create()
    assert isinstance(conf, DictConfig)
    conf.a = 1
    conf.b = OmegaConf.create()
    assert isinstance(conf.b, DictConfig)
    conf.b.c = "${a}"
    assert conf.b.c == conf.a  # type: ignore


@pytest.mark.parametrize(  # type: ignore
    "cfg,key,expected",
    [
        ({"a": 10, "b": "${a}"}, "b", 10),
        ({"a": 10, "b": "${a}", "c": "${b}"}, "c", 10),
        ({"bar": 10, "foo": ["${bar}"]}, "foo.0", 10),
        ({"foo": None, "bar": "${foo}"}, "bar", None),
        ({"list": ["bar"], "foo": "${list.0}"}, "foo", "bar"),
        ({"list": ["${ref}"], "ref": "bar"}, "list.0", "bar"),
    ],
)
def test_interpolations(cfg: Dict[str, Any], key: str, expected: Any) -> None:
    c = OmegaConf.create(cfg)
    assert OmegaConf.select(c, key) == expected


@pytest.mark.parametrize(  # type: ignore
    "cfg,expected_dict",
    [
        pytest.param(
            """
            a: 1
            b: a
            c: ${${b}}
            """,
            {"c": 1},
            id="basic_nesting",
        ),
        pytest.param(
            """
            x: 1
            y: 2
            op: plus
            z: ${plus:${x},${y}}
            t: ${${op}:${x},${y}}
            """,
            {"z": 3, "t": 3},
            id="nesting_with_resolver",
        ),
        pytest.param(
            """
            a:
                b: 1
                c: 2
                d: ${a.b}
            b: c
            c: ${a.${b}}
            d: ${${b}}
            f: a
            g: ${${f}.d}
            """,
            {"c": 2, "d": 2, "g": 1},
            id="member_access",
        ),
        pytest.param(
            """
            a: def
            b: abc_{${a}}
            """,
            {"b": "abc_{def}"},
            id="braces_in_string",
        ),
    ],
)
def test_nested_interpolations(
    restore_resolvers: Any, cfg: str, expected_dict: Dict[str, Any]
) -> None:
    os.environ["OMEGACONF_NESTED_INTERPOLATIONS_TEST"] = "test123"
    OmegaConf.register_resolver("plus", lambda x, y: x + y, variables_as_strings=False)
    c = OmegaConf.create(cfg)
    for key, expected in expected_dict.items():
        assert OmegaConf.select(c, key) == expected


def test_illegal_character_in_interpolation() -> None:
    c = OmegaConf.create(
        """
            a: A
            b: ${env:x.A}
            c: ${env:x.${a}}
            """
    )
    backup = os.environ.pop("x.A", None)
    try:
        with pytest.raises(ValidationError):
            c.b
    finally:
        if backup is not None:
            os.environ["x.A"] = backup

    with pytest.raises(InterpolationSyntaxError):
        c.c


@pytest.mark.parametrize(  # type: ignore
    "cfg,key",
    [
        # All these examples have non-matching braces.
        pytest.param({"a": "PATH", "b": "${env:${a}"}, "b", id="env_not_closed"),
        pytest.param({"a": 1, "b": 2, "c": "${a ${b}"}, "c", id="a_not_closed"),
        pytest.param({"a": 1, "b": 2, "c": "${a} ${b"}, "c", id="b_not_closed"),
    ],
)
def test_nested_interpolation_errors(cfg: Dict[str, Any], key: str) -> None:
    c = OmegaConf.create(cfg)
    with pytest.raises(InterpolationSyntaxError):
        getattr(c, key)


def test_interpolation_with_missing() -> None:
    cfg = OmegaConf.create({"out_file": "${x.name}.txt", "x": {"name": "???"}})
    assert OmegaConf.is_missing(cfg, "out_file")


def test_assign_to_interpolation() -> None:
    cfg = OmegaConf.create(
        {"foo": 10, "bar": "${foo}", "typed_bar": IntegerNode("${foo}")}
    )
    assert OmegaConf.is_interpolation(cfg, "bar")
    assert cfg.bar == 10
    assert cfg.typed_bar == 10

    # assign regular field
    cfg.bar = 20
    assert not OmegaConf.is_interpolation(cfg, "bar")

    with pytest.raises(ValidationError):
        cfg.typed_bar = "nope"
    cfg.typed_bar = 30

    assert cfg.foo == 10
    assert cfg.bar == 20
    assert cfg.typed_bar == 30


def test_merge_with_interpolation() -> None:
    cfg = OmegaConf.create(
        {"foo": 10, "bar": "${foo}", "typed_bar": IntegerNode("${foo}")}
    )

    assert OmegaConf.merge(cfg, {"bar": 20}) == {"foo": 10, "bar": 20, "typed_bar": 10}
    assert OmegaConf.merge(cfg, {"typed_bar": 30}) == {
        "foo": 10,
        "bar": 10,
        "typed_bar": 30,
    }

    with pytest.raises(ValidationError):
        OmegaConf.merge(cfg, {"typed_bar": "nope"})


def _get_expected_exc(expected: Any) -> Tuple[bool, bool, Optional[Exception]]:
    """
    Helper function to obtain information about expected exceptions.

    :param expected: The expected value of a variable, as in `TEST_CONFIG_DATA`.
        If *creating* a config with this variable is expected to raise an exception,
        then this value should be a tuple `(False, Exception)`.
        If *accessing* this variable is expected to raise an exception, then this
        value should be a tuple `(True, Exception)`.
    :return: A tuple `(can_create, can_access, exception)` where:
        * `can_create` indicates whether a config can be created with this variable
        * `can_access` indicates whether this variable can be accessed
        * `exception` is the expected exception (None if both booleans are False)
    """
    can_create = can_access = True
    exception = None
    if (
        isinstance(expected, tuple)
        and len(expected) == 2
        and isinstance(expected[1], type)
        and issubclass(expected[1], Exception)
    ):
        can_create, exception = expected
        can_access = False
    return can_create, can_access, exception


# Config data used to run many interpolation tests. Each 3-element tuple
# contains the config key, its value , and its expected value after
# interpolations are resolved (for exceptions, see `_get_expected_exc()`).
# If the expected value is the ellipsis ... then it is expected to be the
# same as the definition.
# Order matters! (each entry should only depend on those above)
TEST_CONFIG_DATA: List[Tuple[str, Any, Any]] = [
    # Not interpolations (just building blocks for below).
    ("prim_str", "hi", ...),
    ("prim_str_space", "hello world", ...),
    ("id", "identity", ...),
    ("id_partial", "entity", ...),
    ("prim_list", [-1, "a", 1.1], ...),
    ("prim_dict", {"a": 0, "b": 1}, ...),
    ("FalsE", {"TruE": True}, ...),  # used to test keys with bool names
    # Primitive types.
    ("null", "${identity:null}", None),
    ("true", "${identity:TrUe}", True),
    ("false", "${identity:falsE}", False),
    ("truefalse", "${identity:true_false}", "true_false"),
    ("unquoted_str_space", "${identity:hello world}", "hello world"),
    ("unquoted_str_esc_space", r"${identity:\ hello\ world\ }", " hello world "),
    ("unquoted_str_esc_comma", r"${identity:hello\, world}", "hello, world"),
    ("unquoted_other_char", f"${{identity:{chr(200)}}}", chr(200)),
    ("unquoted_emoji", f"${{identity:{chr(129299)}}}", chr(129299)),
    ("unquoted_dot", "${identity:.}", "."),
    ("unquoted_esc", r"${identity:\{}", "{"),
    ("quoted_str_single", "${identity:'!@#$%^&*()[]:.,\"'}", '!@#$%^&*()[]:.,"',),
    ("quoted_str_double", '${identity:"!@#$%^&*()[]:.,\'"}', "!@#$%^&*()[]:.,'",),
    ("quote_outer_ws_single", "${identity: '  a \t'}", "  a \t"),
    ("int", "${identity:123}", 123),
    ("int_pos", "${identity:+123}", 123),
    ("int_neg", "${identity:-123}", -123),
    ("int_underscore", "${identity:1_000}", 1000),
    ("int_underscore_bad_1", "${identity:1_000_}", "1_000_"),
    ("int_underscore_bad_2", "${identity:1__000}", "1__000"),
    ("int_underscore_bad_3", "${identity:_1000}", "_1000"),
    ("int_zero_start", "${identity:007}", "007"),
    ("float", "${identity:1.1}", 1.1),
    ("float_no_int", "${identity:.1}", 0.1),
    ("float_no_decimal", "${identity:1.}", 1.0),
    ("float_plus", "${identity:+1.01}", 1.01),
    ("float_minus", "${identity:-.2}", -0.2),
    ("float_bad_1", "${identity:1.+2}", "1.+2"),
    ("float_bad_2", r"${identity:1\.2}", r"1\.2"),
    ("float_exp_1", "${identity:-1e2}", -100.0),
    ("float_exp_2", "${identity:+1E-2}", 0.01),
    ("float_exp_3", "${identity:1_0e1_0}", 10e10),
    ("float_exp_4", "${identity:1.07e+2}", 107.0),
    ("float_exp_bad_1", "${identity:e-2}", "e-2"),
    ("float_exp_bad_2", "${identity:01e2}", "01e2"),
    ("float_exp_bad_3", "${identity:1e+03}", "1e+03"),
    ("float_inf", "${identity:inf}", math.inf),
    ("float_plus_inf", "${identity:+inf}", math.inf),
    ("float_minus_inf", "${identity:-inf}", -math.inf),
    ("float_nan", "${identity:nan}", math.nan),
    ("float_plus_nan", "${identity:+nan}", math.nan),
    ("float_minus_nan", "${identity:-nan}", math.nan),
    # Node interpolations.
    ("list_access_1", "${prim_list.0}", -1),
    ("list_access_2", "${identity:${prim_list.1},${prim_list.2}}", ["a", 1.1]),
    ("dict_access", "${prim_dict.a}", 0),
    ("bool_like_keys", "${FalsE.TruE}", True),
    ("invalid_type", "${prim_dict.${float}}", (True, InterpolationTypeError)),
    # Resolver interpolations.
    ("env_int", "${env:OMEGACONF_TEST_ENV_INT}", 123),
    ("env_missing_str", "${env:OMEGACONF_TEST_MISSING,miss}", "miss"),
    ("env_missing_int", "${env:OMEGACONF_TEST_MISSING,123}", 123),
    ("env_missing_float", "${env:OMEGACONF_TEST_MISSING,1e-2}", 0.01),
    ("env_missing_quoted_int", "${env:OMEGACONF_TEST_MISSING,'1'}", "1"),
    ("space_in_args", "${identity:a, b c}", ["a", "b c"]),
    ("list_as_input", "${identity:[a, b], 0, [1.1]}", [["a", "b"], 0, [1.1]]),
    ("dict_as_input", "${identity:{'a': 1.1, b: b}}", {"a": 1.1, "b": "b"}),
    (
        "dict_typo_colons",
        "${identity:{'a': 1.1, b:: b}}",
        (True, InterpolationSyntaxError),
    ),
    ("dict_unhashable", "${identity:{[0]: 1}}", (True, TypeError)),
    ("missing_resolver", "${MiSsInG_ReSoLvEr:0}", (True, UnsupportedInterpolationType)),
    ("non_str_resolver", "${${bool}:}", (True, InterpolationTypeError)),
    ("resolver_special", "${infnannulltruefalse:}", "ok"),
    # Unmatched braces.
    ("missing_brace", "${identity:${prim_str}", (True, InterpolationSyntaxError)),
    ("extra_brace", "${identity:${prim_str}}}", "hi}"),
    # String interpolations (top-level).
    ("str_top_basic", "bonjour ${prim_str}", "bonjour hi"),
    ("str_top_quoted_single", "'bonjour ${prim_str}'", "'bonjour hi'",),
    ("str_top_quoted_double", '"bonjour ${prim_str}"', '"bonjour hi"',),
    (
        "str_top_keep_quotes_double",
        '"My name is ${prim_str}", I said.',
        '"My name is hi", I said.',
    ),
    (
        "str_top_keep_quotes_single",
        "'My name is ${prim_str}', I said.",
        "'My name is hi', I said.",
    ),
    ("str_top_any_char", "${prim_str} !@\\#$%^&*})][({,/?;", "hi !@\\#$%^&*})][({,/?;"),
    ("str_top_missing_end_quote_single", "'${prim_str}", "'hi"),
    ("str_top_missing_end_quote_double", '"${prim_str}', '"hi',),
    ("str_top_missing_start_quote_double", '${prim_str}"', 'hi"'),
    ("str_top_missing_start_quote_single", "${prim_str}'", "hi'"),
    ("str_top_middle_quote_single", "I'd like ${prim_str}", "I'd like hi"),
    ("str_top_middle_quote_double", 'I"d like ${prim_str}', 'I"d like hi'),
    ("str_top_middle_quotes_single", "I like '${prim_str}'", "I like 'hi'"),
    ("str_top_esc_inter", r"Esc: \${prim_str}", "Esc: ${prim_str}",),
    ("str_top_esc_inter_wrong_1", r"Wrong: $\{prim_str\}", r"Wrong: $\{prim_str\}",),
    ("str_top_esc_inter_wrong_2", r"Wrong: \${prim_str\}", r"Wrong: ${prim_str\}",),
    ("str_top_esc_backslash", r"Esc: \\${prim_str}", r"Esc: \hi",),
    ("str_top_quoted_braces", r"Braced: \{${prim_str}\}", r"Braced: \{hi\}",),
    ("str_top_leading_dollars", r"$$${prim_str}", "$$hi"),
    ("str_top_trailing_dollars", r"${prim_str}$$$$", "hi$$$$"),
    ("str_top_leading_escapes", r"\\\\\${prim_str}", r"\\${prim_str}"),
    ("str_top_trailing_escapes", "${prim_str}" + "\\" * 5, "hi" + "\\" * 3),
    ("str_top_concat_interpolations", "${true}${float}", "True1.1"),
    # Quoted strings (within interpolations).
    (
        "str_no_other",
        "${identity:hi_${prim_str_space}}",
        (True, InterpolationSyntaxError),
    ),
    (
        "str_quoted_double",
        '${identity:"I say "${prim_str_space}}',
        (True, InterpolationSyntaxError),
    ),
    (
        "str_quoted_single",
        "${identity:'I say '${prim_str_space}}",
        (True, InterpolationSyntaxError),
    ),
    (
        "str_quoted_mixed",
        "${identity:'I '\"say \"${prim_str_space}}",
        (True, InterpolationSyntaxError),
    ),
    ("str_quoted_int", "${identity:'123'}", "123"),
    ("str_quoted_null", "${identity:'null'}", "null"),
    ("str_quoted_bool", "${identity:'truE', \"FalSe\"}", ["truE", "FalSe"]),
    ("str_quoted_list", "${identity:'[a,b, c]'}", "[a,b, c]"),
    ("str_quoted_dict", '${identity:"{a:b, c: d}"}', "{a:b, c: d}"),
    ("str_quoted_inter", "${identity:'${null}'}", "None"),
    (
        "str_quoted_inter_nested",
        "${identity:'${identity:\"L=${prim_list}\"}'}",
        "L=[-1, 'a', 1.1]",
    ),
    ("str_quoted_esc_single_1", r"${identity:'ab\'cd\'\'${prim_str}'}", "ab'cd''hi"),
    ("str_quoted_esc_single_2", "${identity:'\"\\\\\\${foo}\\ '}", r'"\${foo}\ '),
    ("str_quoted_esc_double", r'${identity:"ab\"cd\"\"${prim_str}"}', 'ab"cd""hi'),
    ("str_quoted_esc_double_2", '${identity:"\'\\\\\\${foo}\\ "}', r"'\${foo}\ "),
    ("str_quoted_backslash_noesc_single", r"${identity:'a\b'}", r"a\b"),
    ("str_quoted_backslash_noesc_double", r'${identity:"a\b"}', r"a\b"),
    (
        "str_legal_noquote",
        r"${identity:a./-%#?&@,\ \,\:b\{\}\[\]  \ }",
        ["a./-%#?&@", " ,:b{}[]   "],
    ),
    ("str_equal_noquote", "${identity:a,=b}", ["a", "=b"],),
    ("str_quoted_equal", "${identity:a,'=b'}", ["a", "=b"]),
    ("str_quoted_too_many_1", "${identity:''a'}", (True, InterpolationSyntaxError)),
    ("str_quoted_too_many_2", "${identity:'a''}", (True, InterpolationSyntaxError)),
    ("str_quoted_too_many_3", "${identity:''a''}", (True, InterpolationSyntaxError)),
    # Unquoted strings (within interpolations).
    ("str_dollar", "${identity:$}", "$"),
    ("str_dollar_inter", "${identity:$$${prim_str}}", (True, InterpolationSyntaxError)),
    ("str_backslash_noesc", r"${identity:ab\cd}", r"ab\cd"),
    ("str_esc_inter_1", r"${identity:\${foo\}}", "${foo}"),
    ("str_esc_inter_2", r"${identity:\${}", "${"),
    ("str_esc_brace", r"${identity:$\{foo\}}", "${foo}"),
    ("str_esc_backslash", r"${identity:\\}", "\\"),
    ("str_esc_quotes", "${identity:\\'\\\"}", "'\""),
    ("str_esc_many", r"${identity:\\,\,\{,\]\null}", ["\\", ",{", r"]\null"]),
    ("str_esc_mixed", r"${identity:\,\:\\\{foo\}\[\]}", r",:\{foo}[]"),
    # Structured interpolations.
    ("list", "${identity:[0, 1]}", [0, 1]),
    (
        "dict",
        "${identity:{0: 1, 'a': 'b', 1.1: 1e2, null: 0.1, true: false, -inf: true}}",
        {0: 1, "a": "b", 1.1: 100.0, None: 0.1, True: False, -math.inf: True},
    ),
    ("empties", "${identity:[],{}}", [[], {}]),
    (
        "structured_mixed",
        "${identity:10,str,3.14,true,false,inf,[1,2,3], 'quoted', \"quoted\", 'a,b,c'}",
        [
            10,
            "str",
            3.14,
            True,
            False,
            math.inf,
            [1, 2, 3],
            "quoted",
            "quoted",
            "a,b,c",
        ],
    ),
    (
        "structured_deep",
        '${identity:{null: [0, 3.14, false], true: {"a": [0, 1, 2], "b": {}}}}',
        {None: [0, 3.14, False], True: {"a": [0, 1, 2], "b": {}}},
    ),
    # Chained interpolations.
    ("null_chain", "${null}", None),
    ("true_chain", "${true}", True),
    ("int_chain", "${int}", 123),
    ("list_chain_1", "${${prim_list}.0}", (True, InterpolationTypeError)),
    ("dict_chain_1", "${${prim_dict}.a}", (True, InterpolationTypeError)),
    ("prim_list_copy", "${prim_list}", [-1, "a", 1.1]),  # for below
    ("prim_dict_copy", "${prim_dict}", {"a": 0, "b": 1}),  # for below
    ("list_chain_2", "${prim_list_copy.0}", (True, ConfigKeyError)),
    ("dict_chain_2", "${prim_dict_copy.a}", (True, ConfigKeyError)),
    # Nested interpolations.
    ("ref_prim_str", "prim_str", "prim_str"),
    ("nested_simple", "${${ref_prim_str}}", "hi"),
    ("plans", {"plan A": "awesome plan", "plan B": "crappy plan"}, ...),
    ("selected_plan", "plan A", ...),
    (
        "nested_dotted",
        r"I choose: ${plans.${selected_plan}}",
        "I choose: awesome plan",
    ),
    ("nested_deep", "${identity:${${identity:${ref_prim_str}}}}", "hi"),
    ("nested_resolver", "${${id}:a, b, c}", ["a", "b", "c"]),
    (
        "nested_resolver_combined",
        "${id${id_partial}:a, b, c}",
        (True, InterpolationSyntaxError),
    ),
    # ##### Unusual / edge cases below #####
    # Unquoted `.` and/or `:` on the left of a string interpolation.
    (
        "str_other_left",
        "${identity:.:${prim_str_space}}",
        (True, InterpolationSyntaxError),
    ),
    # Quoted interpolation (=> not actually an interpolation).
    ("fake_interpolation", "'${prim_str}'", "'hi'"),
    # Same as previous, but combined with a "real" interpolation.
    (
        "fake_and_real_interpolations",
        "'${'${identity:prim_str}'}'",
        (True, InterpolationSyntaxError),
    ),
    # Un-matched top-level opening brace in quoted ${
    (
        "interpolation_in_quoted_str",
        "'${'${identity:prim_str}",
        (True, InterpolationSyntaxError),
    ),
    # Special IDs as keys.
    ("None", {"True": 1}, ...),
    ("special_key_exact_spelling", "${None.True}", 1),
    ("special_key_alternate_not_a_container", "${null.true}", (True, ConfigKeyError)),
    ("special_key_alternate_missing", "${NuLL.trUE}", (True, ConfigKeyError)),
    ("special_key_quoted", "${'None'.'True'}", (True, InterpolationSyntaxError)),
    ("special_key_quoted_bad", "${'None.True'}", (True, InterpolationSyntaxError)),
    # Resolvers with special IDs (resolvers are registered with all of these strings).
    ("int_resolver_quoted", "${'0':1,2,3}", (True, InterpolationSyntaxError)),
    ("int_resolver_noquote", "${0:1,2,3}", (True, InterpolationSyntaxError)),
    ("float_resolver_quoted", "${'1.1':1,2,3}", (True, InterpolationSyntaxError)),
    ("float_resolver_noquote", "${1.1:1,2,3}", (True, InterpolationSyntaxError)),
    ("float_resolver_exp", "${1e1:1,2,3}", (True, InterpolationSyntaxError)),
    ("bool_resolver_bad_case", "${FALSE:1,2,3}", ["FALSE", 1, 2, 3]),
    ("bool_resolver_good_case", "${True:1,2,3}", ["True", 1, 2, 3]),
    ("null_resolver", "${null:1,2,3}", ["null", 1, 2, 3]),
    # Special IDs as default values to `env:` resolver.
    ("env_missing_null_quoted", "${env:OMEGACONF_TEST_MISSING,'null'}", "null"),
    ("env_missing_null_noquote", "${env:OMEGACONF_TEST_MISSING,null}", None),
    ("env_missing_bool_quoted", "${env:OMEGACONF_TEST_MISSING,'True'}", "True"),
    ("env_missing_bool_noquote", "${env:OMEGACONF_TEST_MISSING,True}", True),
    # Special IDs as dictionary keys.
    (
        "dict_special_null",
        "${identity:{null: null, 'null': 'null'}}",
        {None: None, "null": "null"},
    ),
    (
        "dict_special_bool",
        "${identity:{true: true, 'false': 'false'}}",
        {True: True, "false": "false"},
    ),
    # Having an unquoted string made only of `.` and `:`.
    ("str_otheronly_noquote", "${identity:a, .:}", (True, InterpolationSyntaxError)),
    # Using an integer as config key.
    ("0", 42, ...),
    ("1", {"2": 12}, ...),
    ("int_key_in_interpolation_noquote", "${0}", 42),
    ("int_key_in_interpolation_quoted", "${'0'}", (True, InterpolationSyntaxError)),
    ("int_key_in_interpolation_x2_noquote", "${1.2}", 12),
    (
        "int_key_in_interpolation_x2_quoted",
        "${'1.2'}",
        (True, InterpolationSyntaxError),
    ),
]


@pytest.mark.parametrize(  # type: ignore
    "key,expected",
    [
        pytest.param(key, definition if expected is ... else expected, id=key)
        for key, definition, expected in TEST_CONFIG_DATA
    ],
)
def test_all_interpolations(restore_resolvers: Any, key: str, expected: Any) -> None:
    dbg_test_access_only = False  # debug flag to not test against expected value
    os.environ["OMEGACONF_TEST_ENV_INT"] = "123"
    os.environ.pop("OMEGACONF_TEST_MISSING", None)
    OmegaConf.register_resolver(
        "identity",
        lambda *args: args[0] if len(args) == 1 else list(args),
        variables_as_strings=False,
    )
    OmegaConf.register_resolver(
        "0", lambda *args: ["0"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "1.1", lambda *args: ["1.1"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "1e1", lambda *args: ["1e1"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "null", lambda *args: ["null"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "FALSE", lambda *args: ["FALSE"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "True", lambda *args: ["True"] + list(args), variables_as_strings=False
    )
    OmegaConf.register_resolver(
        "infnannulltruefalse", lambda: "ok", variables_as_strings=False
    )

    cfg_dict = {}
    for cfg_key, definition, exp in TEST_CONFIG_DATA:
        can_create, can_access, exception = _get_expected_exc(exp)
        if can_create or cfg_key == key:
            assert cfg_key not in cfg_dict, f"duplicated key: {cfg_key}"
            cfg_dict[cfg_key] = definition
        if cfg_key == key:
            break
    can_create, can_access, exception = _get_expected_exc(expected)
    if can_create:
        cfg = OmegaConf.create(cfg_dict)
    else:
        with pytest.raises(exception):
            OmegaConf.create(cfg_dict)

    if can_access:
        if dbg_test_access_only:
            # Only test that we can access, not that it yields the correct value.
            # This is a debug flag to use when testing new grammars without
            # corresponding visitor code.
            getattr(cfg, key)
        elif expected is math.nan:
            # Special case since nan != nan.
            assert math.isnan(getattr(cfg, key))
        else:
            assert getattr(cfg, key) == expected
    elif can_create:
        with pytest.raises(exception):
            getattr(cfg, key)
