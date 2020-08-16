- Add ability to nest interpolations, e.g. ${env:{$var}} or ${foo.${bar}.${baz}}
- The `env` resolver does not cache its output anymore, i.e. `${env:VAR}` will yield a new value if environment variable `VAR` is modified between consecutive accesses
- The `env` resolver now attempts to parse the string representation of environment variables in a way that is consistent with the interpolation grammar. This enables more advanced use cases (e.g. setting environment variables that represent lists or dictionaries, possibly with interpolations: `export VAR='[1, 2, {foo: ${foo}}]'`).
- `register_resolver()` has new arguments to enable more advanced custom resolver behavior:
    * `args_as_strings=False` makes it possible for custom resolvers to take non-string inputs
    * `use_cache=False` disables the cache
    * `config_arg` can be used to give the resolver access to the whole config object
    * `parent_arg` can be used to give the resolver access to the parent of the key being processed
