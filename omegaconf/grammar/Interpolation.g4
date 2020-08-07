// Regenerate parser by running 'python setup.py antlr' at project root.

// Maintenance guidelines when modifying this grammar:
// - Make sure that `OTHER_CHARS` is updated to exclude any new character you may
//   handle in either implicit or explicit lexer tokens.
// - To test the parsing abilities of the modified grammer before writing all the
//   support visitor code, change the test
//        `tests/test_interpolation.py::test_all_interpolations`
//   by setting `dbg_test_access_only = True`, and run it. You will also probably
//   need to comment / hijack the code accesssing the visitor. Tests that expect
//   errors raised from the visitor will obviously fail.
// - Keep up-to-date the comments in the visitor (in `interpolation_parser.py`)
//   that contain grammar excerpts (within each `visit...()` method).
// - Remember to update the documentation (including the tutorial notebook)

// Note that this grammar does *not* attempt to parse floats, and instead relies on
// the visitor to cast strings as floats as needed. This helps keep the grammar simple.

grammar Interpolation;

// Top-level: we allow pretty much everything with interpolations in the middle
// (including strings that contain no interpolations, to un-escape e.g. "a=$\{b\}")
root: toplevel EOF;
toplevel: toplevel_str | (toplevel_str? (interpolation toplevel_str?)+);
toplevel_str: (NULL | BOOL | INT | ID | ESC | WS | OTHER_CHARS | DOT | ',' | ':' | '{' | '}' | '[' | ']' | '\'' | '"')+;

// Interpolations.
interpolation: interpolation_resolver | interpolation_node;
interpolation_resolver: '${' WS? (interpolation | NULL | BOOL | ID) WS? ':' sequence? '}';
interpolation_node: '${' WS? config_key (DOT config_key)* WS? '}';
config_key: interpolation | (NULL | BOOL | INT | ID | ESC | OTHER_CHARS)+;

// Data structures.
sequence: item (',' item)*;
bracketed_list: '[' sequence? ']';
dictionary: '{' (key_value (',' key_value)*)? '}';
key_value: item ':' item;

// Individual items used as resolver arguments or within data structures.
item: WS? item_no_outer_ws WS?;
item_no_outer_ws: interpolation | dictionary | bracketed_list
                // Allow adding whitespaces within quotes for quotable items.
                | item_quotable | '\'' WS? item_quotable WS? '\'' | '"' WS? item_quotable WS? '"';
item_quotable: NULL | BOOL | INT | ID | ESC | OTHER_CHARS | DOT  // single primitive,
    | ((NULL | BOOL | INT | ID | ESC | OTHER_CHARS | DOT)        // or concatenation of multiple primitives
       (NULL | BOOL | INT | ID | ESC | OTHER_CHARS | WS | DOT)*  // (possibly with spaces in the middle)
       (NULL | BOOL | INT | ID | ESC | OTHER_CHARS | DOT));

// *** Lexer rules ***

// Special keywords.
NULL: [Nn][Uu][Ll][Ll];  // null
BOOL:
      [Tt][Rr][Uu][Ee]      // true
    | [Ff][Aa][Ll][Ss][Ee]; // false

// Integers.
// Note: we allow integers starting with zero(s), as calling `int()` on such a
// representation works, Python accepts them in exponents, and it allows parsing
// of 1.000000001 into two integers instead of multiple characters.
fragment DIGIT: [0-9];
fragment INT_UNSIGNED: DIGIT (('_')? DIGIT)*;  // 0, 7, 1_000
INT: [+-]? INT_UNSIGNED;  // 3, -3, +3

// ID (tpyically resolver names).
fragment ALPHA: [a-zA-Z];
ID : (ALPHA | '_') (ALPHA | DIGIT |'_')*;

// Escaped characters.
ESC: ('\\.' | '\\,' | '\\:' | '\\{' | '\\}' | '\\[' | '\\]' | '\\\'' | '\\"' | '\\ ' | '\\\t')+;

// Whitespaces.
WS: (' ' | '\t')+;

// Dot character.
DOT: '.';

// Finally, match remaining characters (grouping together those that are not used above).
// Note that:
//  - `$` and `\` are parsed alone (=ungrouped) because otherwise e.g. '$\{' may not be
//    properly recognized as an escaped interpolation.
//  -  `+` and `-` are included in OTHER_CHARS: this does not break the parsing
//     of INT because if they are concatenated with any other character from OTHER_CHARS
//     then they cannot be part of an INT.
OTHER_CHARS: [$\\] | (~[a-zA-Z_$\\0-9.,:{}[\]'" \t])+;