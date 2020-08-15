import math
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    Iterable,
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
    InterpolationTypeError,
)

if TYPE_CHECKING:
    from .base import Container, Node  # noqa F401

try:
    from omegaconf.grammar.gen.InterpolationLexer import InterpolationLexer
    from omegaconf.grammar.gen.InterpolationParser import InterpolationParser
    from omegaconf.grammar.gen.InterpolationParserVisitor import (
        InterpolationParserVisitor,
    )

except ModuleNotFoundError:  # pragma: no cover
    print(
        "Error importing OmegaConf's generated parsers, run `python setup.py antlr` to regenerate.",
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
        # Note: for now we raise an error to be safe. However this is mostly a
        # performance warning, so in the future this may be relaxed if we need
        # to change the grammar in such a way that this warning cannot be
        # avoided (another option would be to switch to SLL parsing mode).
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


class InterpolationVisitor(InterpolationParserVisitor):
    def __init__(
        self,
        container: "Container",
        resolve_args: Dict[str, Any],
        **kw: Dict[Any, Any],
    ):
        """
        Constructor.

        :param container: The config container to use when resolving interpolations from
            the visitor.
        :param resolve_args: A dictionary indicating which keyword arguments to use when
            calling the `resolve_interpolation()` and `resolve_complex_interpolation()`
            methods of `container`. It is expected to contain values for the following
            keyword arguments:
                `key`, `parent`, `throw_on_missing` and `throw_on_resolution_failure`
        :param kw: Additional keyword arguments to be forwarded to parent class.
        """
        super().__init__(**kw)
        self.container = container
        self.resolve_args = resolve_args

    def aggregateResult(self, aggregate: List[Any], nextResult: Any) -> List[Any]:
        aggregate.append(nextResult)
        return aggregate

    def defaultResult(self) -> List[Any]:
        return []

    def visitConfigKey(self, ctx: InterpolationParser.ConfigKeyContext) -> str:
        from ._utils import _get_value

        # interpolation | ID | LIST_INDEX
        assert ctx.getChildCount() == 1
        child = ctx.getChild(0)
        if isinstance(child, InterpolationParser.InterpolationContext):
            res = _get_value(self.visitInterpolation(child))
            if not isinstance(res, str):
                raise InterpolationTypeError(
                    f"The following interpolation is used to denote a config key and "
                    f"thus should return a string, but instead returned `{res}` of "
                    f"type `{type(res)}`: {ctx.getChild(0).getText()}"
                )
            return res
        else:
            assert isinstance(child, TerminalNode) and isinstance(
                child.symbol.text, str
            )
            return child.symbol.text

    def visitConfigValue(
        self, ctx: InterpolationParser.ConfigValueContext
    ) -> Union[str, Optional["Node"]]:
        assert ctx.getChildCount() == 2  # toplevel EOF
        assert isinstance(ctx.getChild(0), InterpolationParser.ToplevelContext)
        return self.visitToplevel(ctx.getChild(0))

    def visitDictValue(
        self, ctx: InterpolationParser.DictValueContext
    ) -> Dict[Any, Any]:
        # BRACE_OPEN (keyValuePair (COMMA keyValuePair)*)? BRACE_CLOSE
        assert ctx.getChildCount() >= 2
        return dict(
            self.visitKeyValuePair(ctx.getChild(i))
            for i in range(1, ctx.getChildCount() - 1, 2)
        )

    def visitElement(self, ctx: InterpolationParser.ElementContext) -> Any:
        # primitive | listValue | dictValue | interpolation
        assert ctx.getChildCount() == 1
        return self.visit(ctx.getChild(0))

    def visitInterpolation(
        self, ctx: InterpolationParser.InterpolationContext
    ) -> Optional["Node"]:
        from .base import Node  # noqa F811

        assert ctx.getChildCount() == 1  # interpolationNode | interpolationResolver
        ret = self.visit(ctx.getChild(0))
        assert ret is None or isinstance(ret, Node)
        return ret

    def visitInterpolationNode(
        self, ctx: InterpolationParser.InterpolationNodeContext
    ) -> Optional["Node"]:
        # INTERPOLATION_OPEN configKey (DOT configKey)* INTERPOLATION_CLOSE;
        assert ctx.getChildCount() >= 3
        res = [self.visit(child) for child in list(ctx.getChildren())[1:-1:2]]
        return self.container.resolve_simple_interpolation(
            inter_type="str:", inter_key=(".".join(res),), **self.resolve_args
        )

    def visitInterpolationResolver(
        self, ctx: InterpolationParser.InterpolationResolverContext
    ) -> Optional["Node"]:
        from ._utils import _get_value

        # INTERPOLATION_OPEN (interpolation | ID) COLON sequence? BRACE_CLOSE;
        resolver_name = None
        inter_key = []
        inputs_str = []
        for child in ctx.getChildren():
            if (
                isinstance(child, TerminalNode)
                and child.symbol.type == InterpolationLexer.ID
            ):
                assert resolver_name is None
                resolver_name = child.symbol.text
            elif isinstance(child, InterpolationParser.InterpolationContext):
                assert resolver_name is None
                resolver_name = _get_value(self.visitInterpolation(child))
                if not isinstance(resolver_name, str):
                    raise InterpolationTypeError(
                        f"The name of a resolver must be a string, but the interpolation "
                        f"{child.getText()} resolved to `{resolver_name}` which is of type "
                        f"{type(resolver_name)}"
                    )
            elif isinstance(child, InterpolationParser.SequenceContext):
                assert resolver_name is not None
                for val, txt in self.visitSequence(child):
                    inter_key.append(val)
                    inputs_str.append(txt)
            else:
                assert isinstance(child, TerminalNode)

        assert resolver_name is not None
        return self.container.resolve_simple_interpolation(
            inter_type=resolver_name + ":",
            inter_key=tuple(inter_key),
            inputs_str=tuple(inputs_str),
            **self.resolve_args,
        )

    def visitKeyValuePair(
        self, ctx: InterpolationParser.KeyValuePairContext
    ) -> Tuple[Any, Any]:
        from ._utils import _get_value

        assert ctx.getChildCount() == 3  # (ID | interpolation) COLON element
        key_node = ctx.getChild(0)
        if isinstance(key_node, TerminalNode):
            key = key_node.symbol.text
        else:
            assert isinstance(key_node, InterpolationParser.InterpolationContext)
            key = _get_value(self.visitInterpolation(key_node))
            # Forbid using `nan` as dictionary key. This can screw up things due to
            # `nan` not being equal to `nan` (ex: when attempting to sort keys).
            if isinstance(key, float) and math.isnan(key):
                raise InterpolationTypeError("cannot use `NaN` as dictionary key")
        value = _get_value(self.visitElement(ctx.getChild(2)))
        return key, value

    def visitListValue(self, ctx: InterpolationParser.ListValueContext) -> List[Any]:
        # BRACKET_OPEN sequence? BRACKET_CLOSE;
        assert ctx.getChildCount() in (2, 3)
        if ctx.getChildCount() == 2:
            return []
        sequence = ctx.getChild(1)
        assert isinstance(sequence, InterpolationParser.SequenceContext)
        return list(val for val, _ in self.visitSequence(sequence))  # ignore raw text

    def visitPrimitive(self, ctx: InterpolationParser.PrimitiveContext) -> Any:
        # QUOTED_VALUE |
        # (ID | NULL | INT | FLOAT | BOOL | OTHER_CHAR | COLON | ESC | WS | interpolation)+
        if ctx.getChildCount() == 1:
            child = ctx.getChild(0)
            if isinstance(child, InterpolationParser.InterpolationContext):
                return self.visitInterpolation(child)
            assert isinstance(child, TerminalNode)
            symbol = child.symbol
            # Parse primitive types.
            if symbol.type == InterpolationLexer.QUOTED_VALUE:
                return self._resolve_quoted_string(symbol.text)
            elif symbol.type in (
                InterpolationLexer.ID,
                InterpolationLexer.OTHER_CHAR,
                InterpolationLexer.COLON,
            ):
                return symbol.text
            elif symbol.type == InterpolationLexer.NULL:
                return None
            elif symbol.type == InterpolationLexer.INT:
                return int(symbol.text)
            elif symbol.type == InterpolationLexer.FLOAT:
                return float(symbol.text)
            elif symbol.type == InterpolationLexer.BOOL:
                return symbol.text.lower() == "true"
            elif symbol.type == InterpolationLexer.ESC:
                return self._unescape([child])
            elif symbol.type == InterpolationLexer.WS:
                # A single WS should have been "consumed" by another token.
                raise AssertionError("WS should never be reached")
            assert False, symbol.type
        # Concatenation of multiple items ==> un-escape the concatenation.
        return self._unescape(ctx.getChildren())

    def visitSequence(
        self, ctx: InterpolationParser.SequenceContext
    ) -> Generator[Any, None, None]:
        from ._utils import _get_value

        assert ctx.getChildCount() >= 1  # element (COMMA element)*
        for i, child in enumerate(ctx.getChildren()):
            if i % 2 == 0:
                assert isinstance(child, InterpolationParser.ElementContext)
                # Also preserve the original text representation of `child` so
                # as to allow backward compatibility with old resolvers (registered
                # with `args_as_strings=True`). Note that we cannot just cast
                # the value to string later as for instance `null` would become "None".
                yield _get_value(self.visitElement(child)), child.getText()
            else:
                assert (
                    isinstance(child, TerminalNode)
                    and child.symbol.type == InterpolationLexer.COMMA
                )

    def visitSingleElement(self, ctx: InterpolationParser.SingleElementContext) -> Any:
        # element EOF
        assert ctx.getChildCount() == 2
        return self.visit(ctx.getChild(0))

    def visitToplevel(
        self, ctx: InterpolationParser.ToplevelContext
    ) -> Union[str, Optional["Node"]]:
        # toplevelStr | (toplevelStr? (interpolation toplevelStr?)+)
        vals = self.visitChildren(ctx)
        if len(vals) == 1 and isinstance(
            ctx.getChild(0), InterpolationParser.InterpolationContext
        ):
            from .base import Node  # noqa F811

            # Single interpolation: return the resulting node "as is".
            ret = vals[0]
            assert ret is None or isinstance(ret, Node), ret
            return ret
        # Concatenation of multiple components.
        return "".join(map(str, vals))

    def visitToplevelStr(self, ctx: InterpolationParser.ToplevelStrContext) -> str:
        # (ESC | ESC_INTER | TOP_CHAR | TOP_STR)+
        return self._unescape(ctx.getChildren())

    def _resolve_quoted_string(self, quoted: str) -> str:
        """
        Parse a quoted string.
        """
        from .nodes import StringNode

        # Identify quote type.
        assert len(quoted) >= 2 and quoted[0] == quoted[-1]
        quote_type = quoted[0]
        assert quote_type in ["'", '"']

        # Un-escape quotes and backslashes within the string (the two kinds of
        # escapable characters in quoted strings). We do it in two passes:
        #   1. Replace `\"` with `"` (and similarly for single quotes)
        #   2. Replace `\\` with `\`
        # The order is important so that `\\"` is replaced with an escaped quote `\"`.
        # We also remove the start and end quotes.
        esc_quote = f"\\{quote_type}"
        quoted_content = (
            quoted[1:-1].replace(esc_quote, quote_type).replace("\\\\", "\\")
        )

        # Parse the string.
        quoted_val = self.container.resolve_interpolation(
            value=StringNode(
                value=quoted_content, key=None, parent=None, is_optional=False,
            ),
            **self.resolve_args,
        )

        # Cast result to string.
        return str(quoted_val)

    def _unescape(
        self,
        seq: Iterable[Union[TerminalNode, InterpolationParser.InterpolationContext]],
    ) -> str:
        """
        Concatenate all symbols / interpolations in `seq`, unescaping symbols as needed.

        Interpolations are resolved and cast to string *WITHOUT* escaping their result
        (it is assumed that whatever escaping is required was already handled during the
        resolving of the interpolation).
        """
        chrs = []
        for node in seq:
            if isinstance(node, TerminalNode):
                s = node.symbol
                if s.type == InterpolationLexer.ESC:
                    chrs.append(s.text[1::2])
                elif s.type == InterpolationLexer.ESC_INTER:
                    chrs.append(s.text[1:])
                else:
                    chrs.append(s.text)
            else:
                assert isinstance(node, InterpolationParser.InterpolationContext)
                chrs.append(str(self.visitInterpolation(node)))
        return "".join(chrs)


def parse(
    value: str, parser_rule: str = "configValue", lexer_mode: str = "TOPLEVEL"
) -> ParserRuleContext:
    """
    Parse interpolated string `value` (and return the parse tree).
    """
    error_listener = OmegaConfErrorListener()
    istream = InputStream(value)
    lexer = InterpolationLexer(istream)
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    lexer.mode(getattr(InterpolationLexer, lexer_mode))
    stream = CommonTokenStream(lexer)
    parser = InterpolationParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    # The two lines below could be enabled in the future if we decide to switch
    # to SLL prediction mode. Warning though, it has not been fully tested yet!
    # from antlr4 import PredictionMode
    # parser._interp.predictionMode = PredictionMode.SLL

    return getattr(parser, parser_rule)()
