import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)

from antlr4 import CommonTokenStream, InputStream, ParserRuleContext, TerminalNode
from antlr4.error.ErrorListener import ErrorListener

from .errors import (
    InterpolationAmbiguityError,
    InterpolationAttemptingFullContextError,
    InterpolationContextSensitivityError,
    InterpolationSyntaxError,
)

if TYPE_CHECKING:
    from .base import Node  # noqa F401


try:
    from omegaconf.grammar.gen.InterpolationLexer import InterpolationLexer
    from omegaconf.grammar.gen.InterpolationParser import InterpolationParser
    from omegaconf.grammar.gen.InterpolationVisitor import InterpolationVisitor

except ModuleNotFoundError:  # pragma: no cover
    print(
        "Error importing generated parsers, run `python setup.py antlr` to regenerate.",
        file=sys.stderr,
    )
    sys.exit(1)


class OmegaConfErrorListener(ErrorListener):  # type: ignore
    def syntaxError(
        self,
        recognizer: Any,
        offending_symbol: Any,
        line: Any,
        column: Any,
        msg: Any,
        e: Any,
    ) -> None:
        raise InterpolationSyntaxError(str(e) if msg is None else msg) from e

    def reportAmbiguity(
        self,
        recognizer: Any,
        dfa: Any,
        startIndex: Any,
        stopIndex: Any,
        exact: Any,
        ambigAlts: Any,
        configs: Any,
    ) -> None:
        raise InterpolationAmbiguityError()

    def reportAttemptingFullContext(
        self,
        recognizer: Any,
        dfa: Any,
        startIndex: Any,
        stopIndex: Any,
        conflictingAlts: Any,
        configs: Any,
    ) -> None:
        raise InterpolationAttemptingFullContextError()

    def reportContextSensitivity(
        self,
        recognizer: Any,
        dfa: Any,
        startIndex: Any,
        stopIndex: Any,
        prediction: Any,
        configs: Any,
    ) -> None:
        raise InterpolationContextSensitivityError()


class ResolveInterpolationVisitor(InterpolationVisitor):
    def __init__(
        self, resolve_func: Callable[..., Optional["Node"]], **kw: Dict[Any, Any]
    ):
        """
        The `resolve_func` argument is a function that will be called to
        resolve simple interpolations, i.e. any non-nested interpolation of the form
        "${a.b.c}" or "${foo:a,b,c}". It must take the three keyword arguments
        `inter_type`, `inter_key` and `inputs_str`.
        """
        super().__init__(**kw)
        self._resolve_func = resolve_func

    def _resolve_string_interpolation(self, ctx: ParserRuleContext) -> str:
        """Helper function to resolve all variants of string interpolations"""
        assert ctx.getChildCount() >= 2
        rval = "".join(self.visitChildren(ctx))
        return rval

    def visitBoolean(self, ctx: InterpolationParser.BooleanContext) -> bool:
        assert ctx.getChildCount() == 1  # BOOL
        child = ctx.getChild(0)
        assert (
            isinstance(child, TerminalNode)
            and child.symbol.type == InterpolationLexer.BOOL
            and child.symbol.text.lower() in ["true", "false"]
        )
        return bool(child.symbol.text.lower() == "true")

    def visitDirect_interpolation(
        self, ctx: InterpolationParser.Direct_interpolationContext
    ) -> Optional["Node"]:
        # '${' id_maybe_interpolated ('.' id_maybe_interpolated)* '}'
        assert ctx.getChildCount() >= 3
        res = self.visitChildren(ctx)[1:-1:2]  # `:2` to skip dots
        assert all(isinstance(x, str) for x in res), res
        return self._resolve_func(inter_type="str:", inter_key=(".".join(res),))

    def visitFloating_point(
        self, ctx: InterpolationParser.Floating_pointContext
    ) -> float:
        assert ctx.getChildCount() == 1  # FLOAT
        child = ctx.getChild(0)
        assert (
            isinstance(child, TerminalNode)
            and child.symbol.type == InterpolationLexer.FLOAT
        )
        return float(child.symbol.text)

    def visitId_maybe_interpolated(
        self, ctx: InterpolationParser.Id_maybe_interpolatedContext
    ) -> str:
        assert ctx.getChildCount() == 1  # key
        # Identifiers must be strings.
        return str(self.visitChildren(ctx)[0])

    def visitInteger(self, ctx: InterpolationParser.IntegerContext) -> int:
        assert ctx.getChildCount() == 1  # INT
        child = ctx.getChild(0)
        assert (
            isinstance(child, TerminalNode)
            and child.symbol.type == InterpolationLexer.INT
        )
        return int(child.symbol.text)

    def visitItem(self, ctx: InterpolationParser.ItemContext) -> Any:
        assert ctx.getChildCount() >= 1  # (WS)* item_nows (WS)*
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.Item_nowsContext):
                return self.visitItem_nows(child)
            else:
                assert (
                    isinstance(child, TerminalNode)
                    and child.symbol.type == InterpolationLexer.WS
                )
        assert False

    def visitItem_nows(self, ctx: InterpolationParser.Item_nowsContext) -> Any:
        # primitive | interpolation | list_of_items | dict_of_items
        assert ctx.getChildCount() == 1
        return self.visitChildren(ctx)[0]

    def visitInterpolation(self, ctx: InterpolationParser.InterpolationContext) -> Any:
        assert ctx.getChildCount() == 1  # simple_interpolation | string_interpolation
        return self.visitChildren(ctx)[0]

    def visitKey(self, ctx: InterpolationParser.KeyContext) -> Any:
        # primitive | simple_interpolation | string_interpolation_no_other
        assert ctx.getChildCount() == 1
        return self.visitChildren(ctx)[0]

    def visitOther_char(self, ctx: InterpolationParser.Other_charContext) -> str:
        assert ctx.getChildCount() == 1  # '.' | ':'
        child = ctx.getChild(0)
        assert isinstance(child, TerminalNode)
        ret = child.getText()
        assert isinstance(ret, str)
        return ret

    def visitPrimitive(
        self, ctx: InterpolationParser.PrimitiveContext
    ) -> Optional[Union[bool, int, float, str]]:
        # boolean | null | integer | floating_point | string
        assert ctx.getChildCount() == 1
        ret = self.visitChildren(ctx)[0]
        assert ret is None or isinstance(ret, (bool, int, float, str))
        return ret

    def visitResolver_interpolation(
        self, ctx: InterpolationParser.Resolver_interpolationContext
    ) -> Optional["Node"]:
        from ._utils import _get_value

        # '${' id_maybe_interpolated ':' sequence_of_items '}'
        assert ctx.getChildCount() == 5
        inter_type = str(self.visit(ctx.getChild(1))) + ":"
        inter_key = []
        inputs_str = []
        for val, txt in self.visitSequence_of_items(ctx.getChild(3)):
            inter_key.append(_get_value(val))
            inputs_str.append(txt)
        return self._resolve_func(
            inter_type=inter_type,
            inter_key=tuple(inter_key),
            inputs_str=tuple(inputs_str),
        )

    def visitRoot(self, ctx: InterpolationParser.RootContext) -> Any:
        assert ctx.getChildCount() == 2  # item EOF
        return self.visitChildren(ctx)[0]

    def visitSequence_of_items(
        self, ctx: InterpolationParser.Sequence_of_itemsContext
    ) -> Generator[Any, None, None]:
        # (item (',' item)*)?
        for i, child in enumerate(ctx.getChildren()):
            if i % 2 == 0:
                assert isinstance(child, InterpolationParser.ItemContext)
                # Also preserve the original text representation of `child` so
                # as to allow backward compatibility with old resolvers (registered
                # with `variables_as_strings=True`). Note that we cannot just cast
                # the value to string later as for instance `null` would become "None".
                yield self.visitItem(child), child.getText()
            else:
                assert isinstance(child, TerminalNode) and child.getText() == ","

    def visitSimple_interpolation(
        self, ctx: InterpolationParser.Simple_interpolationContext
    ) -> Optional["Node"]:
        from .base import Node  # noqa F811

        assert ctx.getChildCount() == 1  # direct_interpolation | resolver_interpolation
        ret = self.visitChildren(ctx)[0]
        assert ret is None or isinstance(ret, Node)
        return ret

    def visitString(self, ctx: InterpolationParser.StringContext) -> str:
        assert ctx.getChildCount() == 1  # ID | BASIC_STR | QUOTED_STR
        child = ctx.getChild(0)
        assert isinstance(child, TerminalNode)
        text, ptype = child.symbol.text, child.symbol.type
        assert isinstance(text, str)
        if ptype == InterpolationLexer.ID:
            return text
        elif ptype == InterpolationLexer.BASIC_STR:
            # Unquote commas & space.
            return text.replace("\\ ", " ").replace("\\,", ",")
        else:
            assert ptype == InterpolationLexer.QUOTED_STR, ptype
            return text[1:-1]

    def visitString_interpolation(
        self, ctx: InterpolationParser.String_interpolationContext
    ) -> str:
        # string_interpolation_no_other | string_interpolation_other_left | string_interpolation_other_right
        assert ctx.getChildCount() == 1
        ret = self.visitChildren(ctx)[0]
        assert isinstance(ret, str)
        return ret

    def visitString_interpolation_no_other(
        self, ctx: InterpolationParser.String_interpolation_no_otherContext
    ) -> str:
        return self._resolve_string_interpolation(ctx)

    def visitString_interpolation_other_right(
        self, ctx: InterpolationParser.String_interpolation_other_rightContext
    ) -> str:
        return self._resolve_string_interpolation(ctx)

    def visitString_interpolation_other_left(
        self, ctx: InterpolationParser.String_interpolation_other_leftContext
    ) -> str:
        return self._resolve_string_interpolation(ctx)

    def aggregateResult(self, aggregate: List[Any], nextResult: Any) -> List[Any]:
        aggregate.append(nextResult)
        return aggregate

    def defaultResult(self) -> List[Any]:
        return []

    def visitPrimitive_or_simple(
        self, ctx: InterpolationParser.Primitive_or_simpleContext
    ) -> str:

        assert ctx.getChildCount() == 1  # primitive | simple_interpolation
        child = ctx.getChild(0)
        child_val = self.visit(child)
        if isinstance(child_val, str):
            # Result is a string: we can re-use it directly.
            return child_val
        elif isinstance(child, InterpolationParser.PrimitiveContext):
            # Here we want to keep the original string representation when possible,
            # to avoid situations where we might e.g. transform "true" into "True".
            ret = child.getText()
            assert isinstance(ret, str)
            return ret
        else:
            # Anything else: convert to string.
            return str(child_val)

    def visitList_of_items(
        self, ctx: InterpolationParser.List_of_itemsContext
    ) -> List[Any]:
        assert ctx.getChildCount() == 3  # '[' sequence_of_items ']'
        return list(val for val, txt in self.visit(ctx.getChild(1)))

    def visitDict_of_items(
        self, ctx: InterpolationParser.Dict_of_itemsContext
    ) -> Dict[Any, Any]:
        # '{' (key_value (',' key_value)*)? '}';
        assert ctx.getChildCount() >= 2
        ret = {}
        for i in range(1, ctx.getChildCount() - 1, 2):
            key, value = self.visit(ctx.getChild(i))
            ret[key] = value
        return ret

    def visitKey_value(
        self, ctx: InterpolationParser.Key_valueContext
    ) -> Tuple[Any, Any]:
        # key_value: (WS)* key (WS)* ':' item;
        found_key = False
        key = None
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.KeyContext):
                assert not found_key
                key = self.visitKey(child)
                found_key = True
            elif isinstance(child, InterpolationParser.ItemContext):
                assert found_key
                return key, self.visitItem(child)
            else:
                assert isinstance(child, TerminalNode)
        assert False

    def visitNull(self, ctx: InterpolationParser.NullContext) -> None:
        assert ctx.getChildCount() == 1  # NULL
        child = ctx.getChild(0)
        assert (
            isinstance(child, TerminalNode)
            and child.symbol.type == InterpolationLexer.NULL
        )
        return None


def parse(value: str) -> InterpolationParser.RootContext:
    """
    Parse interpolated string `value` (return the parse tree).
    """
    error_listener = OmegaConfErrorListener()
    istream = InputStream(value)
    lexer = InterpolationLexer(istream)
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    stream = CommonTokenStream(lexer)
    parser = InterpolationParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)
    return parser.root()  # type: ignore
