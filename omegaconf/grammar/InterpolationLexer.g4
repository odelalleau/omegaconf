// Regenerate lexer and parser by running 'python setup.py antlr' at project root.
// See `InterpolationParser.g4` for some important information regarding how to
// properly maintain this grammar.

lexer grammar InterpolationLexer;

// Re-used Fragments.
fragment DIGIT: [0-9];
fragment INT_UNSIGNED: ('0' | [1-9] (('_')? DIGIT)*);
fragment CHAR: [a-zA-Z];
fragment ID_: (CHAR|'_') (CHAR|DIGIT|'_')*;
fragment INTERPOLATION_OPEN_: '${';
fragment WS_: [ \t]+;

//////////////
// TOPLEVEL //
//////////////

mode TOPLEVEL;

INTERPOLATION_OPEN: INTERPOLATION_OPEN_ -> pushMode(INTERPOLATION);

ESC_INTER: '\\${';
ESC: ('\\\\')+;

// The backslash and dollar characters must not be grouped with others, so that
// we can properly detect the tokens above.
TOP_CHAR: [\\$];
TOP_STR: ~[\\$]+;  // anything else

///////////////////
// INTERPOLATION //
///////////////////

mode INTERPOLATION;

BEGIN_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION);
COLON: ':' WS_* -> mode(ARGS);
INTERPOLATION_CLOSE: '}' -> popMode;

DOT: '.';
ID: ID_;
LIST_INDEX: INT_UNSIGNED;
WS: WS_ -> skip;

//////////
// ARGS //
//////////

mode ARGS;

ARGS_INTER_OPEN: INTERPOLATION_OPEN_ -> type(INTERPOLATION_OPEN), pushMode(INTERPOLATION);
BRACE_OPEN: '{' WS_* -> pushMode(ARGS);  // must keep track of braces to detect end of interpolation
BRACE_CLOSE: WS_* '}' -> popMode;

// Special keywords.
NULL: [Nn][Uu][Ll][Ll];  // null
BOOL:
      [Tt][Rr][Uu][Ee]      // true
    | [Ff][Aa][Ll][Ss][Ee]; // false

// Numbers.
INT: [+-]? INT_UNSIGNED;

fragment POINT_FLOAT: INT_UNSIGNED? '.' DIGIT+ | INT_UNSIGNED '.';
fragment EXPONENT_FLOAT: (INT_UNSIGNED | POINT_FLOAT) [eE] [+-]? INT_UNSIGNED;
FLOAT: [+-]? (POINT_FLOAT | EXPONENT_FLOAT | [Ii][Nn][Ff] | [Nn][Aa][Nn]);

// Strings.

ARGS_ID: ID_ -> type(ID);

BRACKET_OPEN: '[' WS_*;
BRACKET_CLOSE: WS_* ']';

COMMA: WS_* ',' WS_*;
ARGS_COLON: WS_* ':' WS_* -> type(COLON);
OTHER_CHAR: [/\-\\+.$*];  // other characters allowed in unquoted strings
ARGS_WS: WS_ -> type(WS);

QUOTED_VALUE:
      '\'' ('\\\''|.)*? '\'' // Single quotes, can contain escaped single quote : /'
    | '"' ('\\"'|.)*? '"' ;  // Double quotes, can contain escaped double quote : /"