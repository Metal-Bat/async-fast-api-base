---
tags: [architecture]
---

# Safe expressions and explicit transforms

Status: accepted for BPMS-008 on 2026-09-22.

## Decision

Workflow expressions use a dependency-free interpreter built on Python 3.14's `ast.parse` in
expression mode. The parsed tree is never passed to `compile` or `eval`. Application code first
walks an allowlist to resolve types, then a separate interpreter evaluates those same allowed
nodes against plain dictionaries. This keeps the language independent of Python object attributes,
imports, bytecode, filesystem, network, database sessions, and framework objects.

The project already depends on `jsonschema`, but JSON Schema validates data rather than evaluating
conditions. No installed package provides a bounded typed expression runtime. Adding a general
template, JavaScript, CEL, or policy engine would add a second grammar and Python 3.14 compatibility
surface without removing the need for project-specific schemas, reachability, work budgets, and
redaction. The local interpreter is deliberately small and covered as a public application module.

## Language contract

Expressions may use literals (`null`, booleans, integers, finite numbers, strings, and bounded list
literals), parentheses, `and`, `or`, `not`, unary signs, arithmetic (`+`, `-`, `*`, `/`, `%`), typed
comparisons, membership, and the registered functions below. String `+` requires two strings;
numeric arithmetic requires integer/number operands. Ordered comparison requires two numbers or
two strings. `is null` and `is not null` are the only identity comparisons.

| Function | Input | Result |
| --- | --- | --- |
| `starts_with`, `ends_with` | two strings | boolean |
| `lower`, `upper` | one string | string |
| `length` | string, array, or object | integer |
| `contains` | string/array and a member | boolean |
| `choose` | boolean and two compatible values | the branch type |

Names resolve only through four typed namespaces:

- `request` contains fields declared by the request/form JSON Schema.
- `process` contains documented process context such as `priority` and `status` plus explicitly
  declared context bindings.
- `current_user` contains `ref_id`, `is_superuser`, and `work_group_refs`; it never contains a user
  entity, password data, tokens, permissions internals, or connection secrets.
- `steps.<step_key>.outputs.<port_key>` contains declared outputs from steps that dominate the
  current step. Forward, branch-only, and otherwise unreachable outputs are absent from the schema
  and fail compilation.

Subscripts, comprehensions, lambdas, assignments, f-strings, arbitrary calls, private/dunder paths,
and object method or attribute access are rejected. Unknown names and fields are rejected with a
line, zero-based column, stable code, and expected/actual schemas when a type comparison exists.
Conditions must compile to boolean. Decision expressions must compile to string. Form calculation
expressions use the form data schema as `request` and must match the calculated field schema.

## Bounds and deterministic behavior

The default limits are 1,024 source characters, 128 AST nodes, depth 16, 512 evaluation work
units, 256 collection members, and 4,096 characters per string. Compilation rejects excess before
execution. Evaluation counts visited nodes and validates result depth, work, collection size, and
string size. The language has no clock, randomness, mutation, iteration construct, I/O, or ambient
global values, so equal source and context yield equal values. Duration is observational metadata
and does not affect the result.

Evaluation records contain namespace/result type and size summaries plus duration and a stable
error code. Raw values are never included. Callers must log the record rather than source context
or exceptions.

## Transform contract

The original transform handler version 1 remains immutable. Handler version 2 adds completion
metadata and validated options for these conversion keys:

| Key | Accepted value | Result and failure rule |
| --- | --- | --- |
| `string` | scalar/object/array | canonical scalar text or sorted compact JSON; optional one-slot `Value: {}` formatting |
| `integer` | signed decimal string or 64-bit integer | 64-bit integer; fractions, booleans, overflow, whitespace, and exponent syntax fail |
| `decimal` | bounded plain decimal string or number | exact `Decimal`; NaN, infinity, exponent syntax, and excess digits fail |
| `boolean` | boolean or exact lowercase `true`/`false` | boolean; other spellings fail |
| `date` | ISO date | ISO date or bounded `strftime` output |
| `date_time` | timezone-aware ISO date-time | UTC ISO value ending in `Z` or bounded `strftime` output |
| `array` | array or JSON text containing an array | array; non-array JSON fails |
| `object` | object plus JSON Pointer projection map | a new object containing only projected fields |

`null_behavior` is `error`, `preserve`, or `default`. `default` requires a non-null JSON value.
Projection and formatting are accepted only by relevant conversions. Inputs and results share the
expression collection/depth/string safety profile; errors contain only type/size summaries,
duration, and codes such as `transform.integer.invalid` or `transform.limit`.

Workflow publication uses the transform configuration to derive effective input/output JSON
Schemas. A string source can bind to an integer transform input, and its declared integer result
can bind to an integer consumer. The same direct string-to-integer binding remains invalid. The
configuration schema enum supplies designer completion choices without accepting imports or
unregistered conversion names.

## Compatibility and evolution

The implementation uses Python standard-library AST classes available in Python 3.14.7, Pydantic
models already required by the project, and JSON Schema shapes already used by forms and ports.
New syntax, functions, namespace fields, or transform options require behavior tests and a review
of their type and work bounds. Incompatible handler configuration or port changes require a new
handler version and additive catalog migration; published versions are never rewritten.
