// Regenerate lexer and parser by running 'python setup.py antlr' at project root.
// See `InterpolationParser.g4` for some important information regarding how to
// properly maintain this grammar.


lexer grammar InterpolationLexer;

// Re-used Fragments.
fragment DIGIT: [0-9];
fragment CHAR: [a-zA-Z];
fragment ID_: (CHAR|'_') (CHAR|DIGIT|'_')*;
fragment INTERPOLATION_OPEN_: '${';
fragment ESC_INTER_: '\\${';  // escaped interpolation
fragment ESC_BACKSLASH_: '\\\\';  // escaped backslash
fragment WS_: [ \t]+;

/////////////////////////
// DEFAULT (TOP-LEVEL) //
/////////////////////////

INTERPOLATION_OPEN: INTERPOLATION_OPEN_ -> pushMode(INTERPOLATION);

ESC: (ESC_BACKSLASH_)+;
ESC_INTER: ESC_INTER_;
TOP_CHR: [\\$];
TOP_STR: ~[\\$]+;  // anything else

///////////////////
// INTERPOLATION //
///////////////////
mode INTERPOLATION;

BEGIN_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION);
COLON: ':' -> mode(ARGS);
INTERPOLATION_CLOSE: '}' -> popMode;

DOT: '.';
ID: ID_;
LIST_INDEX: '0' | [1-9][0-9]*;
WS: WS_ -> channel(HIDDEN);

//////////
// ARGS //
//////////

mode ARGS;

ARGS_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION);
BRACE_OPEN: '{' -> pushMode(ARGS);  // must keep track of braces to detect end of interpolation
BRACE_CLOSE: '}' -> popMode;

// Special keywords.
NULL: [Nn][Uu][Ll][Ll];  // null
BOOL:
      [Tt][Rr][Uu][Ee]      // true
    | [Ff][Aa][Ll][Ss][Ee]; // false

// Integers.
fragment NZ_DIGIT_: [1-9];
fragment INT_UNSIGNED_: ('0' | NZ_DIGIT_ (('_')? DIGIT)*);
INT: [+-]? INT_UNSIGNED_;

fragment POINT_FLOAT_: INT_UNSIGNED_? '.' DIGIT+ | INT_UNSIGNED_ '.';
fragment EXPONENT_FLOAT_: (INT_UNSIGNED_ | POINT_FLOAT_) [eE] [+-]? INT_UNSIGNED_;
FLOAT: [+-]? (POINT_FLOAT_ | EXPONENT_FLOAT_ | [Ii][Nn][Ff] | [Nn][Aa][Nn]);

// Strings.

ARGS_ESC: (ESC_BACKSLASH_)+ -> type(ESC);
ARGS_ESC_INTER: ESC_INTER_ -> type(ESC_INTER);

ARGS_ID: ID_ -> type(ID);
OTHER_CHAR: [/\-\\+.$*];

BRACKET_OPEN: '[';
BRACKET_CLOSE: ']';

COMMA: ',';
ARGS_COLON: ':' -> type(COLON);

ARGS_WS: WS_ -> channel(HIDDEN);

QUOTED_VALUE:
      '\'' ('\\\''|.)*? '\'' // Single quotes, can contain escaped single quote : /'
    | '"' ('\\"'|.)*? '"' ;  // Double quotes, can contain escaped double quote : /"

// "'