// Regenerate parser by running 'python setup.py antlr' at project root.

// Maintenance guidelines when modifying this grammar:
//
// - For initial testing of the parsing abilities of the modified grammer before
//   writing all the support visitor code, change the test
//        `tests/test_interpolation.py::test_all_interpolations`
//   by setting `dbg_test_access_only = True`, and run it. You will also probably
//   need to comment / hijack the code accesssing the visitor. Tests that expect
//   errors raised from the visitor will obviously fail.
//
// - Keep up-to-date the comments in the visitor (in `interpolation_parser.py`)
//   that contain grammar excerpts (within each `visit...()` method).
//
// - Remember to update the documentation (including the tutorial notebook)

parser grammar InterpolationParser;

// Tokens obtained from the corresponding lexer.
options {tokenVocab = InterpolationLexer;}

// Main rules used to parse OmegaConf strings.
config_value: toplevel EOF;
single_element: element EOF;

// Top-level: strings (that need not be parsed), potentially mixed with interpolations.
toplevel: toplevel_str | (toplevel_str? (interpolation toplevel_str?)+);
toplevel_str: (ESC | ESC_INTER | TOP_CHAR | TOP_STR)+;

// Interpolations.
interpolation: interpolation_node | interpolation_resolver;
interpolation_node: INTERPOLATION_OPEN config_key (DOT config_key)* INTERPOLATION_CLOSE;
interpolation_resolver: INTERPOLATION_OPEN (interpolation | ID) COLON sequence? BRACE_CLOSE;

config_key: interpolation | ID | LIST_INDEX;
sequence: element (COMMA element)*;

// Data structures.
listValue: BRACKET_OPEN sequence? BRACKET_CLOSE;                    // [], [1,2,3], [a,b,[1,2]]
dictValue: BRACE_OPEN (key_value (COMMA key_value)*)? BRACE_CLOSE;  // {}, {a:10,b:20}

key_value: (ID | interpolation) COLON element;

// Individual elements used as resolver arguments or within data structures.
element:
      primitive
    | listValue
    | dictValue
;

primitive:
      QUOTED_VALUE                                  // 'hello world', "hello world"
    | (
          ID                                        // foo_10
        | NULL                                      // null, NULL
        | INT                                       // 0, 10, -20, 1_000_000
        | FLOAT                                     // 3.14, -20.0, 1e-1, -10e3
        | BOOL                                      // true, TrUe, false, False
        | OTHER_CHAR                                // /, -, \, +, ., $, *
        | COLON                                     // :
        | ESC                                       // \\, \, \ , \\t
        | WS                                        // whitespaces
        | interpolation
    )+;