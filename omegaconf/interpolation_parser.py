from typing import Any

from antlr4 import CommonTokenStream, InputStream, ParserRuleContext
from antlr4.error.ErrorListener import ErrorListener

from .errors import (
    InterpolationAmbiguityError,
    InterpolationAttemptingFullContextError,
    InterpolationContextSensitivityError,
    InterpolationSyntaxError,
)

# Import from visitor in order to check the presence of generated grammar files
# files in a single place.
from .interpolation_visitor import (  # type: ignore
    InterpolationLexer,
    InterpolationParser,
)


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
