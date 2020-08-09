// Regenerate parser by running 'python setup.py antlr' at project root.

// Maintenance guidelines when modifying this grammar:
// - To test the parsing abilities of the modified grammer before writing all the
//   support visitor code, change the test
//        `tests/test_interpolation.py::test_all_interpolations`
//   by setting `dbg_test_access_only = True`, and run it. You will also probably
//   need to comment / hijack the code accesssing the visitor. Tests that expect
//   errors raised from the visitor will obviously fail.
// - Keep up-to-date the comments in the visitor (in `interpolation_parser.py`)
//   that contain grammar excerpts (within each `visit...()` method).
// - Remember to update the documentation (including the tutorial notebook)

parser grammar InterpolationParser;

options {tokenVocab = InterpolationLexer;}

// Top-level: strings (that need not be parsed), potentially mixed with interpolations.
root: toplevel EOF;
toplevel: toplevel_str | (toplevel_str? (interpolation toplevel_str?)+);
toplevel_str: (ESC_INTER | TOP_CHR | TOP_STR)+;

// Interpolations.
interpolation: interpolation_node | interpolation_resolver;
interpolation_node: INTERPOLATION_OPEN BEGIN_WS?
                    config_key ((BEGIN_DOT | DOTPATH_DOT) config_key)*
                    BEGIN_WS? INTERPOLATION_CLOSE;
interpolation_resolver: INTERPOLATION_OPEN BEGIN_WS?
                        (interpolation | BEGIN_ID) BEGIN_WS? BEGIN_COLON sequence?
                        ARGS_BRACE_CLOSE;
config_key: interpolation | (BEGIN_ID | BEGIN_STR)+ | DOTPATH_OTHER+;

// Data structures.
sequence: item (ARGS_COMMA item)*;
bracketed_list: ARGS_BRACKET_OPEN sequence? ARGS_BRACKET_CLOSE;
dictionary: ARGS_BRACE_OPEN (key_value (ARGS_COMMA key_value)*)? ARGS_BRACE_CLOSE;
key_value: item ARGS_COLON item;

// Quoted strings.
quoted_single: ARGS_QUOTE_SINGLE
               (interpolation | QSINGLE_ESC | ESC_INTER | QSINGLE_CHR | QSINGLE_STR)+
               QSINGLE_CLOSE;
quoted_double: ARGS_QUOTE_DOUBLE
               (interpolation | QDOUBLE_ESC | ESC_INTER | QDOUBLE_CHR | QDOUBLE_STR)+
               QDOUBLE_CLOSE;

// Individual items used as resolver arguments or within data structures.
item: ARGS_WS? item_no_outer_ws ARGS_WS?;
item_no_outer_ws: interpolation | dictionary | bracketed_list | quoted_single | quoted_double | item_unquoted;
item_unquoted: NULL | BOOL | INT | FLOAT | ARGS_ESC | ESC_INTER | ARGS_STR        // single primitive,
    | ((NULL | BOOL | INT | FLOAT | ARGS_ESC | ESC_INTER | ARGS_STR)              // or concatenation of multiple primitives
       (NULL | BOOL | INT | FLOAT | ARGS_ESC | ESC_INTER | ARGS_STR | ARGS_WS)*   // (possibly with spaces in the middle)
       (NULL | BOOL | INT | FLOAT | ARGS_ESC | ESC_INTER | ARGS_STR));