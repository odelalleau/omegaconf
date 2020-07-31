// Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved

// Regenerate parser by running 'python setup.py antlr' at project root.
// If you make changes here be sure to update the documentation (and update the grammar in command_line_syntax.md)
grammar Interpolation;

// *** Parser rules ***

// High-level.
root: item EOF;
item: (WS)* item_nows (WS)*;
item_nows: primitive | interpolation | list_of_items | dict_of_items;

// Interpolations.
interpolation: simple_interpolation | string_interpolation;
// Simple interpolations are of the form ${..}
simple_interpolation: direct_interpolation | resolver_interpolation;
direct_interpolation: '${' id_maybe_interpolated ('.' id_maybe_interpolated)* '}';  // ${foo}, {foo.bar}
resolver_interpolation: '${' id_maybe_interpolated ':' sequence_of_items '}';  // ${foo:x,y,z}
id_maybe_interpolated: key;  // TODO simplify
// String interpolations combine multiple components into a single string.
// We allow additional characters that can be concatenated without being quoted, in addition to
// those in `STR_NO_DIGIT`. This allows for instance using `http://domain.com:${port}`.
// Note that these additional characters cannot be added to `STR_NO_DIGIT` as otherwise
// some "." and ":" used in interpolations would be "consumed" by the lexer.
other_char: '.' | ':';
string_interpolation: string_interpolation_no_other | string_interpolation_other_left | string_interpolation_other_right;
// The "no other" string interpolation does not contain any character from `other_char`.
// It is used to extract identifiers, so that we can use for instance `${foo_${bar}:arg}`.
// Note that we allow non-string primitive types so as to deal with edge cases like `null${foo}`.
string_interpolation_no_other: primitive_or_simple (primitive_or_simple)+;
// The "other left and "other right" string interpolations are those containing characters
// from `other_char` (respectively starting and not starting with such a character).
string_interpolation_other_left: ((other_char)+ (primitive_or_simple)+)+ (other_char)*;
string_interpolation_other_right: ((primitive_or_simple)+ (other_char)+)+ (primitive_or_simple)*;
primitive_or_simple: primitive | simple_interpolation;

// Containers.
list_of_items: '[' sequence_of_items ']';
sequence_of_items: (item (',' item)*)?;
dict_of_items: '{' (key_value (',' key_value)*)? '}';
key_value: (WS)* key (WS)* ':' item;
key: primitive | simple_interpolation | string_interpolation_no_other;

// Primitive types.
primitive: boolean | null | integer | floating_point | string;
integer: INT;
string: ID | BASIC_STR | QUOTED_STR;
floating_point: FLOAT;
boolean: BOOL;
null: NULL;

// *** Lexer rules ***

// Special keywords.
NULL: [Nn][Uu][Ll][Ll];  // null
BOOL:
      [Tt][Rr][Uu][Ee]      // true
    | [Ff][Aa][Ll][Ss][Ee]; // false

// Integers.
// Note: we disallow integers starting with '0' to minimize potential typos, even
// though calling `int()` on such a representation works, and Python also accepts
// them in exponents (ex: 1.5e007).
fragment DIGIT: [0-9];
fragment NZ_DIGIT: [1-9];
fragment INT_UNSIGNED: '0' | (NZ_DIGIT (('_')? DIGIT)*);  // 0, 7, 1_000
INT: [+-]? INT_UNSIGNED;  // 3, -3, +3

// Floats.
fragment FRACTION: '.' INT_UNSIGNED;
fragment POINT_FLOAT: INT_UNSIGNED? FRACTION | INT_UNSIGNED '.';  // .1, 0.1, 0.
fragment EXPONENT: [eE] [+-]? INT; // e5, E-3
fragment EXPONENT_FLOAT: (INT_UNSIGNED | POINT_FLOAT) EXPONENT;
FLOAT: [+-]? (POINT_FLOAT | EXPONENT_FLOAT | [Ii][Nn][Ff] | [Nn][Aa][Nn]);

// Strings.
fragment ALPHA_: [a-zA-Z] | '_';
fragment ESC_SPACE: '\\ ';
fragment ESC_COMMA: '\\,';
fragment ESC_OUTSIDE: ESC_SPACE | ESC_COMMA;
ID : ALPHA_ (ALPHA_ | DIGIT)*;  // foo, bar2
// Basic strings (= non quoted) are not allowed to start with a digit, so as to
// minimize the risk of typos (ex: 1__000).
// foo, foo_bar, foo/2, foo\ 2, \,foo\,-bar\,baz\, (TODO: more examples)
fragment STR_NO_DIGIT: ALPHA_ | '/' | '-' | '%' | '#' | '?' | '&' | '@' | ESC_COMMA | ESC_SPACE;
fragment STR_TWO_PLUS_CHARS: STR_NO_DIGIT (DIGIT | STR_NO_DIGIT | ' ' | '\t')* (DIGIT | STR_NO_DIGIT)+;
BASIC_STR: STR_NO_DIGIT | STR_TWO_PLUS_CHARS;
QUOTED_STR:
      '\'' ('\\\''|.)*? '\''  // Single quoted string. Can contain escaped single quote.
    | '"' ('\\"'|.)*? '"' ;   // Double quoted string. can contain escaped double quote.
WS: (' ' | '\t');
