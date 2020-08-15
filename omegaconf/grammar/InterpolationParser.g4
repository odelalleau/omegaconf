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
// - Update Hydra's grammar accordingly, and if you added more cases to the test
//   mentioned above, copy the latest version of `TEST_CONFIG_DATA` to Hydra (see
//   Hydra's test: `tests/test_overrides_parser.py::test_omegaconf_interpolations`).
     
// - Keep up-to-date the comments in the visitor (in `interpolation_visitor.py`)
//   that contain grammar excerpts (within each `visit...()` method).
//
// - Remember to update the documentation (including the tutorial notebook)

parser grammar InterpolationParser;
options {tokenVocab = InterpolationLexer;}

// Main rules used to parse OmegaConf strings.

configValue: toplevel EOF;
singleElement: element EOF;

// Top-level: strings (that need not be parsed), potentially mixed with interpolations.

toplevel: toplevelStr | (toplevelStr? (interpolation toplevelStr?)+);
toplevelStr: (ESC | ESC_INTER | TOP_CHAR | TOP_STR)+;

// Elements.

element:
      primitive
    | listValue
    | dictValue
;

// Interpolations.

interpolation: interpolationNode | interpolationResolver;
interpolationNode: INTERPOLATION_OPEN configKey (DOT configKey)* INTERPOLATION_CLOSE;
interpolationResolver: INTERPOLATION_OPEN (interpolation | ID) COLON sequence? BRACE_CLOSE;

configKey: interpolation | ID | LIST_INDEX;
sequence: element (COMMA element)*;

// Data structures.

listValue: BRACKET_OPEN sequence? BRACKET_CLOSE;                          // [], [1,2,3], [a,b,[1,2]]
dictValue: BRACE_OPEN (keyValuePair (COMMA keyValuePair)*)? BRACE_CLOSE;  // {}, {a:10,b:20}
keyValuePair: (ID | interpolation) COLON element;

// Primitive types.

primitive:
      QUOTED_VALUE                               // 'hello world', "hello world"
    | (   ID                                     // foo_10
        | NULL                                   // null, NULL
        | INT                                    // 0, 10, -20, 1_000_000
        | FLOAT                                  // 3.14, -20.0, 1e-1, -10e3
        | BOOL                                   // true, TrUe, false, False
        | OTHER_CHAR                             // /, -, \, +, ., $, *
        | COLON                                  // :
        | ESC                                    // \\, \, \ , \\t
        | WS                                     // whitespaces
        | interpolation
    )+;
