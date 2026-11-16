# V2 interpolation contract

This reference describes interpolation contract version 1 for `run(flow=...)`.
The legacy `run(custom_dataset_function=...)` entry and public
`invoicefile.apply_magic_variable` retain their existing boolean, empty-value,
and source-selection behavior.

## Policy and migration

V2 defaults to `auto` when `system.magic_variable` is omitted. Eligible strings
containing `${...}` opt into strict parsing and resolution. Plain strings remain
unchanged. An existing explicit boolean remains authoritative: `true` selects
`enabled`, and `false` selects `disabled`. Disabled mode preserves literal text,
including malformed expressions, and emits a diagnostic when a placeholder is
left in an eligible field.

The explicit options live in `custom.interpolation`:

```yaml
custom:
  interpolation:
    policy: auto
    missing: error
```

`policy` accepts `auto`, `enabled`, and `disabled`. `missing` accepts `error` and
`omit`. Unknown options and contradictory explicit boolean/policy choices fail.
When migrating a config that contains `magic_variable: false`, remove that flag
to use auto, or replace it with the explicit namespace above.

Config fingerprints preserve the distinction between an omitted magic flag and
explicit false. Repro export retains explicit disabling through a YAML round
trip. Fingerprints created before this policy-aware change can differ for
configs with an omitted flag; regenerate those pre-GA reports before repro export.

## Grammar and source scopes

| Expression | Source |
| --- | --- |
| `${filename}` | Basename of the tile's unique raw input |
| `${invoice:basic:field}` | Original invoice's direct basic field |
| `${invoice:custom:field}` | Original invoice's direct custom field |
| `${invoice:sample:names}` | Original invoice's ordered sample names |
| `${invoice-original:basic:field}` | Explicit original scope; custom and sample forms also apply |
| `${invoice-current:basic:field}` | Current tile invoice; custom and sample forms also apply |
| `${metadata:constant:key}` | Current tile metadata constant's `value` |

The original invoice is an immutable value captured before tile construction.
The current invoice and metadata are captured after the flow, immediately before
interpolation. All fields resolve against these snapshots. Earlier substitutions
and earlier tiles never become inputs to later substitutions. Resolved source
strings are not parsed recursively.

Invoice and metadata expressions work without raw attachments. Filename requires
exactly one raw input in each applicable mode. Zero or multiple raw inputs are an
error only when filename is requested. Select a unique input or use an explicit
invoice/metadata identifier for grouped inputs. A SmartTable row CSV is not a raw
attachment and never supplies filename implicitly.

Outer expression whitespace is ignored. Internal whitespace, extra segments,
empty keys, nested expressions, and unknown sources are invalid. Keys contain
Unicode letters/numbers, `_`, or `-`; they are direct mapping keys. Dots, slashes,
brackets, attribute traversal, and executable expressions are unsupported.
`$${filename}` produces literal `${filename}`. Ordinary braces outside an
expression remain literal. An unclosed opener is an error, including an escaped
opener without its closing brace.

Templates are limited to 16,384 characters and 128 expressions per eligible
field. Expanded fields are limited to 16,384 characters after omission and
literal-separator normalization. Intermediate lengths do not reject a valid
final value. `basic.dataName` has an
additional 1–4,096 character limit and rejects control characters. These are
versioned library limits; the invoice schema can impose tighter constraints.

## Fields and missing values

The output allowlist is `basic.dataName` and `basic.description`, when their
values are strings. All other fields, objects, arrays, identifiers, and non-string
values remain untouched. This is an explicit allowlist, not recursive JSON
interpolation. The later optional feature-description stage may amend description.

Missing sources, absent keys, null, empty strings, and empty lists are distinct
diagnostic reasons. Each fails by default. `missing: omit` explicitly omits those
values. Omission collapses redundant underscore runs only when both neighboring
pieces are template literals. Referenced source text is always preserved,
including leading or trailing underscores. A name that becomes empty still fails.

Zero and false remain scalar values, formatted as `0` and `False`. Unicode code
points are preserved without NFC or NFKC rewriting. Sample names retain their
order and join nonempty strings with `_`; non-string members fail. Objects and
lists cannot be scalar substitutions. Nonfinite numbers fail. Path-looking
values remain labels; interpolation never opens them as filesystem paths.

For active flow interpolation, initial invoice validation defers direct string
value constraints (`pattern`, `enum`, `const`, `format`, `minLength`, and
`maxLength`) only at eligible template destinations. Required fields, types,
and other destinations are still checked before the flow. Aggregate and ancestor
schema constraints remain strict at this stage. Disabled interpolation,
RDEFormat, and direct `Runner.pre_validate()` calls retain full value validation.
Row modes and legacy callbacks retain their existing validation timing.

Every changed invoice is validated against the standard invoice contract and
its `invoice.schema.json` before atomic replacement. Any expression, schema, or
publication failure leaves the invoice unchanged. The generated
[error catalog](../../rdetoolkit/error_catalog.md) documents error remedies.
If cleanup after a failed publication also fails, the original redacted error
is retained. Cleanup is best effort and can leave an unremoved temporary file.

## Registration modes

| Mode | Interpolation stage |
| --- | --- |
| Invoice | After thumbnail and structured export, before feature description |
| ExcelInvoice | Before thumbnail, structured export, and feature description |
| MultiDataTile | Before thumbnail, structured export, and feature description |
| SmartTable | Invoice order for each registration row, including rows without attachments |
| RDEFormat | Not applicable; already formatted registration artifacts omit interpolation |

The optional SmartTable tile containing the original table is precompleted and
omits the flow and interpolation stage. Legacy artifact order is preserved.

## Pure preview

`rdetoolkit.domain.magic` provides `ResolutionContext`, `MagicOptions`,
`resolve_invoice`, and `preview_invoice`. Contexts own immutable JSON snapshots.
The preview returns versioned, deterministic diagnostics without writing files
or returning substituted values. Diagnostics identify destination, expression
offset, source scope/path, tile index, status, and remedy. Values are redacted.

```pycon
>>> from rdetoolkit.domain.magic import ResolutionContext, preview_invoice, resolve_invoice
>>> context = ResolutionContext.from_sources(
...     original_invoice={"custom": {"batch": "B-1"}},
...     current_invoice={"basic": {"dataName": "${invoice:custom:batch}"}},
... )
>>> resolve_invoice(context)["basic"]["dataName"]
'B-1'
>>> preview_invoice(context).diagnostics[0].status
'resolved'

```

Runner `--validate-only` checks available original-invoice template syntax and
reports that per-tile sources are deferred. It does not execute the flow to
manufacture metadata. Runner validation itself writes its normal logs/reports;
use the pure preview API when filesystem immutability is required.

Complete SmartTable row/schema preview and row/column diagnostics remain
dependent on [#734](https://github.com/nims-mdpf/rdetoolkit/issues/734).
The pure preview is groundwork for
[#727](https://github.com/nims-mdpf/rdetoolkit/issues/727); that integration and
the [#704 epic](https://github.com/nims-mdpf/rdetoolkit/issues/704) remain open.

`RuleBasedReplacer` is a separate compatibility API for dotted assignments.
An explicit `mapping_rules`, including `{}`, replaces stored rules. Successful
calls retain the documented source mutation. Missing replacements become empty
strings. Invalid ancestor paths and overlapping parent/child assignments fail
before any mutation. The API remains publicly importable.
