import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

from antlr4 import CommonTokenStream, InputStream, TerminalNode
from antlr4.error.ErrorListener import ErrorListener

from .errors import (
    InterpolationAmbiguityError,
    InterpolationAttemptingFullContextError,
    InterpolationContextSensitivityError,
    InterpolationSyntaxError,
    InterpolationTypeError,
)

if TYPE_CHECKING:
    from .base import Node  # noqa F401

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


class ResolveInterpolationVisitor(InterpolationParserVisitor):
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

    def aggregateResult(self, aggregate: List[Any], nextResult: Any) -> List[Any]:
        aggregate.append(nextResult)
        return aggregate

    def defaultResult(self) -> List[Any]:
        return []

    def visitBracketed_list(
        self, ctx: InterpolationParser.Bracketed_listContext
    ) -> List[Any]:
        # ARGS_BRACKET_OPEN sequence? ARGS_BRACKET_CLOSE
        assert ctx.getChildCount() in (2, 3)
        if ctx.getChildCount() == 2:
            return []
        sequence = ctx.getChild(1)
        assert isinstance(sequence, InterpolationParser.SequenceContext)
        return list(val for val, _ in self.visitSequence(sequence))  # ignore raw text

    def visitConfig_key(self, ctx: InterpolationParser.Config_keyContext) -> str:
        from ._utils import _get_value

        # interpolation | (BEGIN_ID | BEGIN_OTHER)+ | DOTPATH_OTHER+
        if ctx.getChildCount() == 1 and isinstance(
            ctx.getChild(0), InterpolationParser.InterpolationContext
        ):
            res = _get_value(self.visitInterpolation(ctx.getChild(0)))
            if not isinstance(res, str):
                raise InterpolationTypeError(
                    f"The following interpolation is used to denote a config key and "
                    f"thus should return a string, but instead returned `{res}` of "
                    f"type `{type(res)}`: {ctx.getChild(0).getText()}"
                )
            return res
        return "".join(child.symbol.text for child in ctx.getChildren())

    def visitDictionary(
        self, ctx: InterpolationParser.DictionaryContext
    ) -> Dict[Any, Any]:
        # ARGS_BRACE_OPEN (key_value (ARGS_COMMA key_value)*)? ARGS_BRACE_CLOSE
        assert ctx.getChildCount() >= 2
        ret = {}
        for i in range(1, ctx.getChildCount() - 1, 2):
            key, value = self.visitKey_value(ctx.getChild(i))
            ret[key] = value
        return ret

    def visitItem(self, ctx: InterpolationParser.ItemContext) -> Any:
        # ARGS_WS? item_no_outer_ws ARGS_WS?
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.Item_no_outer_wsContext):
                return self.visitItem_no_outer_ws(child)
            else:
                assert (
                    isinstance(child, TerminalNode)
                    and child.symbol.type == InterpolationLexer.ARGS_WS
                )
        assert False

    def visitItem_no_outer_ws(
        self, ctx: InterpolationParser.Item_no_outer_wsContext
    ) -> Any:
        # interpolation | dictionary | bracketed_list | quoted_single | quoted_double | item_unquoted
        assert ctx.getChildCount() == 1
        return self.visit(ctx.getChild(0))

    def visitItem_unquoted(self, ctx: InterpolationParser.Item_unquotedContext) -> Any:
        if ctx.getChildCount() == 1:
            # NULL | BOOL | INT | FLOAT | ESC | ESC_INTER | ARGS_STR
            child = ctx.getChild(0)
            assert isinstance(child, TerminalNode)
            # Parse primitive types.
            if child.symbol.type == InterpolationLexer.NULL:
                return None
            elif child.symbol.type == InterpolationLexer.BOOL:
                return child.symbol.text.lower() == "true"
            elif child.symbol.type == InterpolationLexer.INT:
                return int(child.symbol.text)
            elif child.symbol.type == InterpolationLexer.FLOAT:
                return float(child.symbol.text)
            elif child.symbol.type in (
                InterpolationLexer.ESC,
                InterpolationLexer.ESC_INTER,
            ):
                return self._unescape([child])
            elif child.symbol.type == InterpolationLexer.ARGS_STR:
                return child.symbol.text
            assert False
        # Concatenation of the above (plus potential whitespaces in the middle):
        # just un-escape their string representation.
        return self._unescape(ctx.getChildren())

    def visitInterpolation(
        self, ctx: InterpolationParser.InterpolationContext
    ) -> Optional["Node"]:
        from .base import Node  # noqa F811

        assert ctx.getChildCount() == 1  # interpolation_node | interpolation_resolver
        ret = self.visit(ctx.getChild(0))
        assert ret is None or isinstance(ret, Node)
        return ret

    def visitInterpolation_node(
        self, ctx: InterpolationParser.Interpolation_nodeContext
    ) -> Optional["Node"]:
        # interpolation_open BEGIN_WS? config_key ((BEGIN_DOT | DOTPATH_DOT) config_key)*
        # BEGIN_WS? interpolation_node_end;
        assert ctx.getChildCount() >= 3
        res = []
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.Config_keyContext):
                res.append(self.visitConfig_key(child))
        return self._resolve_func(inter_type="str:", inter_key=(".".join(res),))

    def visitInterpolation_resolver(
        self, ctx: InterpolationParser.Interpolation_resolverContext
    ) -> Optional["Node"]:
        from ._utils import _get_value

        # interpolation_open BEGIN_WS? (interpolation | BEGIN_ID) BEGIN_WS? BEGIN_COLON
        # sequence? ARGS_BRACE_CLOSE
        resolver_name = None
        inter_key = []
        inputs_str = []
        for child in ctx.getChildren():
            if (
                isinstance(child, TerminalNode)
                and child.symbol.type == InterpolationLexer.BEGIN_ID
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
                    inter_key.append(_get_value(val))
                    inputs_str.append(txt)

        assert resolver_name is not None
        return self._resolve_func(
            inter_type=resolver_name + ":",
            inter_key=tuple(inter_key),
            inputs_str=tuple(inputs_str),
        )

    def visitKey_value(
        self, ctx: InterpolationParser.Key_valueContext
    ) -> Tuple[Any, Any]:
        assert ctx.getChildCount() == 3  # item ARGS_COLON item
        key = self.visitItem(ctx.getChild(0))
        value = self.visitItem(ctx.getChild(2))
        return key, value

    def visitQuoted_double(self, ctx: InterpolationParser.Quoted_doubleContext) -> str:
        return self._visitQuoted(ctx)

    def visitQuoted_single(self, ctx: InterpolationParser.Quoted_singleContext) -> str:
        return self._visitQuoted(ctx)

    def visitRoot(
        self, ctx: InterpolationParser.RootContext
    ) -> Union[str, Optional["Node"]]:
        assert ctx.getChildCount() == 2  # toplevel EOF
        toplevel = ctx.getChild(0)
        assert isinstance(toplevel, InterpolationParser.ToplevelContext)
        return self.visitToplevel(toplevel)

    def visitSequence(
        self, ctx: InterpolationParser.SequenceContext
    ) -> Generator[Any, None, None]:
        assert ctx.getChildCount() >= 1  # item (ARGS_COMMA item)*
        for i, child in enumerate(ctx.getChildren()):
            if i % 2 == 0:
                assert isinstance(child, InterpolationParser.ItemContext)
                # Also preserve the original text representation of `child` so
                # as to allow backward compatibility with old resolvers (registered
                # with `variables_as_strings=True`). Note that we cannot just cast
                # the value to string later as for instance `null` would become "None".
                yield self.visitItem(child), child.getText()
            else:
                assert isinstance(child, TerminalNode)

    def visitToplevel(
        self, ctx: InterpolationParser.ToplevelContext
    ) -> Union[str, Optional["Node"]]:
        # toplevel_str | (toplevel_str? (interpolation toplevel_str?)+)
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

    def visitToplevel_str(self, ctx: InterpolationParser.Toplevel_strContext) -> str:
        # ESC_INTER | TOP_BACKSLASH | TOP_DOLLAR | TOP_STR
        return self._unescape(ctx.getChildren())

    def _unescape(self, seq: Iterable[TerminalNode]) -> str:
        """
        Concatenate all symbols in `seq`, unescaping those that need it.
        """
        chrs = []
        for node in seq:
            s = node.symbol
            if s.type == InterpolationLexer.ESC:
                chrs.append(s.text[1::2])
            elif s.type == InterpolationLexer.ESC_INTER:
                chrs.append(s.text[1:])
            else:
                chrs.append(s.text)
        return "".join(chrs)

    def _visitQuoted(
        self,
        ctx: Union[
            InterpolationParser.Quoted_singleContext,
            InterpolationParser.Quoted_doubleContext,
        ],
    ) -> str:
        """
        Visitor for quoted strings (either with single or double quotes).
        """
        # ARGS_QUOTE_*
        # (interpolation | ESC | ESC_INTER | Q*_CHR | Q*_STR)+
        # Q*_CLOSE;
        assert ctx.getChildCount() >= 3
        vals = []
        for child in list(ctx.getChildren())[1:-1]:
            if isinstance(child, InterpolationParser.InterpolationContext):
                vals.append(str(self.visitInterpolation(child)))
            else:
                vals.append(self._unescape([child]))
        return "".join(vals)


def parse(value: str) -> InterpolationParser.RootContext:
    """
    Parse interpolated string `value` (and return the parse tree).
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

    # The two lines below could be enabled in the future if we decide to switch
    # to SLL prediction mode. Warning though, it has not been fully tested yet!
    # from antlr4 import PredictionMode
    # parser._interp.predictionMode = PredictionMode.SLL

    return parser.root()  # type: ignore
