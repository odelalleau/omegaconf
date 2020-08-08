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
toplevel_str: (TOP_ESC_INTER | TOP_BACKSLASH | TOP_DOLLAR | TOP_STR)+;

// Interpolations.
interpolation: interpolation_node | interpolation_resolver;
interpolation_node: interpolation_open BEGIN_WS?
                    config_key ((BEGIN_DOT | DOTPATH_DOT) config_key)*
                    BEGIN_WS? interpolation_node_close;
interpolation_resolver: interpolation_open BEGIN_WS?
                        (interpolation | BEGIN_ID) BEGIN_WS? BEGIN_COLON sequence?
                        ARGS_BRACE_CLOSE;
interpolation_open: TOP_INTERPOLATION_OPEN | BEGIN_NESTED_INTERPOLATION_OPEN | DOTPATH_NESTED_INTERPOLATION_OPEN | ARGS_NESTED_INTERPOLATION_OPEN;
interpolation_node_close: BEGIN_CLOSE | DOTPATH_CLOSE;
config_key: interpolation | (BEGIN_ID | BEGIN_OTHER)+ | DOTPATH_OTHER+;

// Data structures.
sequence: item (ARGS_COMMA item)*;
bracketed_list: ARGS_BRACKET_OPEN sequence? ARGS_BRACKET_CLOSE;
dictionary: ARGS_BRACE_OPEN (key_value (ARGS_COMMA key_value)*)? ARGS_BRACE_CLOSE;
key_value: item ARGS_COLON item;

// Individual items used as resolver arguments or within data structures.
item: ARGS_WS? item_no_outer_ws ARGS_WS?;
item_no_outer_ws: interpolation | dictionary | bracketed_list | item_quotable
                // Allow adding whitespaces within quotes for quotable items.
                | ARGS_QUOTE_SINGLE ARGS_WS? item_quotable ARGS_WS? ARGS_QUOTE_SINGLE
                | ARGS_QUOTE_DOUBLE ARGS_WS? item_quotable ARGS_WS? ARGS_QUOTE_DOUBLE;
item_quotable: NULL | BOOL | INT | FLOAT | ARGS_ESC | ARGS_ESC_INTER | ARGS_STR        // single primitive,
    | ((NULL | BOOL | INT | FLOAT | ARGS_ESC | ARGS_ESC_INTER | ARGS_STR)              // or concatenation of multiple primitives
       (NULL | BOOL | INT | FLOAT | ARGS_ESC | ARGS_ESC_INTER | ARGS_STR | ARGS_WS)*   // (possibly with spaces in the middle)
       (NULL | BOOL | INT | FLOAT | ARGS_ESC | ARGS_ESC_INTER | ARGS_STR));
