// Regenerate lexer and parser by running 'python setup.py antlr' at project root.
// See `InterpolationParser.g4` for some important information regarding how to
// properly maintain this grammar.


lexer grammar InterpolationLexer;

// Re-used Fragments.
fragment DIGIT_: [0-9];
fragment INTERPOLATION_OPEN_: '${';
fragment ESC_INTER_: '\\${';  // escaped interpolation
fragment ESC_BACKSLASH_: '\\\\';  // escaped backslash

/////////////////////////
// DEFAULT (TOP-LEVEL) //
/////////////////////////

INTERPOLATION_OPEN: INTERPOLATION_OPEN_ -> pushMode(INTERPOLATION_BEGIN);

ESC: (ESC_BACKSLASH_)+;
ESC_INTER: ESC_INTER_;
TOP_CHR: [\\$];
TOP_STR: ~[\\$]+;  // anything else

/////////////////////////
// INTERPOLATION_BEGIN //
/////////////////////////

mode INTERPOLATION_BEGIN;

BEGIN_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION_BEGIN);
BEGIN_DOT: '.' -> mode(DOTPATH);
BEGIN_COLON: ':' -> mode(RESOLVER_ARGS);
INTERPOLATION_CLOSE: '}' -> popMode;

// Resolver names must match `ID` (or be an interpolation).
fragment ALPHA_: [a-zA-Z_];
BEGIN_ID : ALPHA_ (ALPHA_ | DIGIT_)*;  // foo, bar_123
BEGIN_WS: [ \t]+;
// Forbidden characters in config key names: `:.${}[]'" \t\`.
// We do not allow escaping of these characters.
BEGIN_STR: ~[a-zA-Z_:.${}[\]'" \t\\]+;

/////////////
// DOTPATH //
/////////////

mode DOTPATH;

DOTPATH_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION_BEGIN);
DOTPATH_INTER_CLOSE: '}' -> type(INTERPOLATION_CLOSE), popMode;

DOTPATH_DOT: '.';
DOTPATH_OTHER: ~[:.${}[\]'" \t\\]+;

///////////////////
// QUOTED_SINGLE //
///////////////////

mode QUOTED_SINGLE;

QSINGLE_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION_BEGIN);
QSINGLE_CLOSE: '\'' -> popMode;

QSINGLE_ESC: ('\\\'' | ESC_BACKSLASH_)+ -> type(ESC);
QSINGLE_ESC_INTER: ESC_INTER_ -> type(ESC_INTER);

QSINGLE_CHR: [\\$];
QSINGLE_STR: (~['\\$])+;

///////////////////
// QUOTED_DOUBLE //
///////////////////

mode QUOTED_DOUBLE;

QDOUBLE_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION_BEGIN);
QDOUBLE_CLOSE: '"' -> popMode;

QDOUBLE_ESC: ('\\"' | ESC_BACKSLASH_)+ -> type(ESC);
QDOUBLE_ESC_INTER: ESC_INTER_ -> type(ESC_INTER);

QDOUBLE_CHR: [\\$];
QDOUBLE_STR: (~["\\$])+;

///////////////////
// RESOLVER_ARGS //
///////////////////

mode RESOLVER_ARGS;

ARGS_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION_BEGIN);
ARGS_BRACE_OPEN: '{' -> pushMode(RESOLVER_ARGS);
ARGS_QUOTE_SINGLE: '\'' -> pushMode(QUOTED_SINGLE);
ARGS_QUOTE_DOUBLE: '"' -> pushMode(QUOTED_DOUBLE);
ARGS_BRACE_CLOSE: '}' -> popMode;

ARGS_ESC: ('\\{' | '\\}' | '\\[' | '\\]' | '\\,' | '\\:' | '\\\'' | '\\"' | '\\ ' | '\\\t' | ESC_BACKSLASH_)+ -> type(ESC);
ARGS_ESC_INTER: ESC_INTER_ -> type(ESC_INTER);

ARGS_BRACKET_OPEN: '[';
ARGS_BRACKET_CLOSE: ']';

ARGS_COMMA: ',';
ARGS_COLON: ':';
ARGS_WS: [ \t]+;

// Special keywords.
NULL: [Nn][Uu][Ll][Ll];  // null
BOOL:
      [Tt][Rr][Uu][Ee]      // true
    | [Ff][Aa][Ll][Ss][Ee]; // false

// Integers.
fragment NZ_DIGIT_: [1-9];
fragment INT_UNSIGNED_: ('0' | NZ_DIGIT_ (('_')? DIGIT_)*);
INT: [+-]? INT_UNSIGNED_;

fragment POINT_FLOAT_: INT_UNSIGNED_? '.' DIGIT_+ | INT_UNSIGNED_ '.';
fragment EXPONENT_FLOAT_: (INT_UNSIGNED_ | POINT_FLOAT_) [eE] [+-]? INT_UNSIGNED_;
FLOAT: [+-]? (POINT_FLOAT_ | EXPONENT_FLOAT_ | [Ii][Nn][Ff] | [Nn][Aa][Nn]);

// Other characters. We keep `$` and `\` ungrouped so that e.g. `\{` and '${'
// can be properly identified.
ARGS_STR: [$\\] | (~[$\\:,{}[\]'" \t])+;