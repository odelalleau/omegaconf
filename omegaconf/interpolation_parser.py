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

    def aggregateResult(self, aggregate: List[Any], nextResult: Any) -> List[Any]:
        aggregate.append(nextResult)
        return aggregate

    def defaultResult(self) -> List[Any]:
        return []

    def visitBracketed_list(
        self, ctx: InterpolationParser.Bracketed_listContext
    ) -> List[Any]:
        assert ctx.getChildCount() in (2, 3)  # '[' sequence? ']'
        if ctx.getChildCount() == 2:
            return []
        sequence = ctx.getChild(1)
        assert isinstance(sequence, InterpolationParser.SequenceContext)
        return list(val for val, _ in self.visitSequence(sequence))  # ignore raw text

    def visitConfig_key(self, ctx: InterpolationParser.Config_keyContext) -> str:
        from ._utils import _get_value

        # interpolation | (NULL | BOOL | INT | ID | ESC | OTHER_CHARS)+
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
        return self._unescape(ctx.getChildren())

    def visitDictionary(
        self, ctx: InterpolationParser.DictionaryContext
    ) -> Dict[Any, Any]:
        assert ctx.getChildCount() >= 2  # '{' (key_value (',' key_value)*)? '}'
        ret = {}
        for i in range(1, ctx.getChildCount() - 1, 2):
            key, value = self.visitKey_value(ctx.getChild(i))
            ret[key] = value
        return ret

    def visitItem(self, ctx: InterpolationParser.ItemContext) -> Any:
        # WS? item_no_outer_ws WS?
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.Item_no_outer_wsContext):
                return self.visitItem_no_outer_ws(child)
            else:
                assert (
                    isinstance(child, TerminalNode)
                    and child.symbol.type == InterpolationLexer.WS
                )
        assert False

    def visitItem_no_outer_ws(
        self, ctx: InterpolationParser.Item_no_outer_wsContext
    ) -> Any:
        if ctx.getChildCount() == 1:
            # interpolation | dictionary | bracketed_list | item_quotable
            return self.visit(ctx.getChild(0))
        # Quoted item: '\'' WS? item_quotable WS? '\'' | '"' WS? item_quotable WS? '"'
        n_children = ctx.getChildCount()
        assert n_children >= 3
        res = []
        for child_idx, child in enumerate(ctx.getChildren()):
            if child_idx == 0 or child_idx == n_children - 1:
                assert isinstance(child, TerminalNode)  # start / end quotes
            elif isinstance(child, TerminalNode):
                assert (
                    child.symbol.type == InterpolationLexer.WS
                )  # leading / trailing whitespace
                res.append(child)
            else:
                assert isinstance(child, InterpolationParser.Item_quotableContext)
                res.extend(child.getChildren())
        return self._unescape(res)

    def visitItem_quotable(self, ctx: InterpolationParser.Item_quotableContext) -> Any:
        if ctx.getChildCount() == 1:
            # NULL | BOOL | INT | ID | ESC | OTHER_CHARS | DOT
            child = ctx.getChild(0)
            assert isinstance(child, TerminalNode)
            # Parse primitive types.
            if child.symbol.type == InterpolationLexer.NULL:
                return None
            elif child.symbol.type == InterpolationLexer.BOOL:
                return child.symbol.text.lower() == "true"
            elif child.symbol.type == InterpolationLexer.INT:
                return int(child.symbol.text)
            elif child.symbol.type == InterpolationLexer.ID:
                return self._maybe_float(child.symbol.text)  # could be e.g. nan / inf
            elif child.symbol.type == InterpolationLexer.ESC:
                return child.symbol.text[1::2]
            elif child.symbol.type in [
                InterpolationLexer.OTHER_CHARS,
                InterpolationLexer.DOT,
            ]:
                return child.symbol.text
            assert False
        # Concatenation of the above (plus potential whitespaces in the middle):
        # first check if it is a float, otherwise un-escape it.
        ret = self._maybe_float(ctx.getText())
        return ret if isinstance(ret, float) else self._unescape(ctx.getChildren())

    def visitInterpolation(
        self, ctx: InterpolationParser.InterpolationContext
    ) -> Optional["Node"]:
        from .base import Node  # noqa F811

        assert ctx.getChildCount() == 1  # interpolation_resolver | interpolation_node
        ret = self.visit(ctx.getChild(0))
        assert ret is None or isinstance(ret, Node)
        return ret

    def visitInterpolation_node(
        self, ctx: InterpolationParser.Interpolation_nodeContext
    ) -> Optional["Node"]:
        assert ctx.getChildCount() >= 3  # '${' WS? config_key (DOT config_key)* WS? '}'
        res = []
        for child in ctx.getChildren():
            if isinstance(child, InterpolationParser.Config_keyContext):
                res.append(self.visitConfig_key(child))
            else:
                assert isinstance(child, TerminalNode)
        return self._resolve_func(inter_type="str:", inter_key=(".".join(res),))

    def visitInterpolation_resolver(
        self, ctx: InterpolationParser.Interpolation_resolverContext
    ) -> Optional["Node"]:
        from ._utils import _get_value

        # '${' WS? (interpolation | NULL | BOOL | ID) WS? ':' sequence? '}'

        resolver_name = None
        inter_key = []
        inputs_str = []
        for child in ctx.getChildren():
            if isinstance(child, TerminalNode) and child.symbol.type in [
                InterpolationLexer.NULL,
                InterpolationLexer.BOOL,
                InterpolationLexer.ID,
            ]:
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
            else:
                assert isinstance(child, TerminalNode)

        assert resolver_name is not None
        return self._resolve_func(
            inter_type=resolver_name + ":",
            inter_key=tuple(inter_key),
            inputs_str=tuple(inputs_str),
        )

    def visitKey_value(
        self, ctx: InterpolationParser.Key_valueContext
    ) -> Tuple[Any, Any]:
        assert ctx.getChildCount() == 3  # key_value: item ':' item
        key = self.visitItem(ctx.getChild(0))
        value = self.visitItem(ctx.getChild(2))
        return key, value

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
        assert ctx.getChildCount() >= 1  # item (',' item)*
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

            # from ._utils import _get_value
            # Single interpolation: return the resulting node "as is".
            ret = vals[0]
            assert ret is None or isinstance(ret, Node), ret
            return ret
        # Concatenation of multiple components.
        return "".join(map(str, vals))

    def visitToplevel_str(self, ctx: InterpolationParser.Toplevel_strContext) -> str:
        # Just un-escape top-level characters.
        return self._unescape(ctx.getChildren())

    def _maybe_float(self, some_str: str) -> Union[float, str]:
        """
        Attempt to cast `some_str` as a float.
        """
        try:
            return float(some_str)
        except ValueError:
            return some_str

    def _unescape(self, seq: Iterable[TerminalNode]) -> str:
        """
        Concatenate all symbols in `seq`, unescaping those that need it.
        """
        chrs = []
        for node in seq:
            s = node.symbol
            if s.type == InterpolationLexer.ESC:
                chrs.append(s.text[1::2])
            else:
                chrs.append(s.text)
        return "".join(chrs)


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

    # The chunk of code below could be enabled in the future if we decide to
    # switch to SLL prediction mode. Warning though, it is not currently tested!
    if False:
        from antlr4 import PredictionMode

        parser._interp.predictionMode = PredictionMode.SLL

    return parser.root()  # type: ignore
