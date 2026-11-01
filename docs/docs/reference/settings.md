# Stage settings, flags and options

This page lists the names rietx uses besides its parameters, plans, diagnostic codes and result fields: stage settings, peak flags, peak origins, reader options, instrument preset fields and indexing search settings.

The entries are generated from `rietx.help`, the one place each is written.
The GUI puts the same sentence beside the same control, so this page and a tooltip cannot disagree.
Parameters are on the [parameter map](parameters.md), plans on [Plan presets](plans.md), diagnostic codes on [Diagnostic codes](diagnostics.md) and result fields on [Result fields](result-fields.md).

## Looking one up in code

`help_for` takes a parameter name and returns the entry whose family claims it.
It matches with `fnmatch`, as a stage's `turn_on` patterns do.

```python
import rietx as rx

entry = rx.help_for("phases.0.atoms.2.biso")
print(entry.title)
print(entry.unit, entry.default)
```

```text
Isotropic displacement parameter
Å² 0.5
```

A name outside the parameter vocabulary returns `None` rather than a guess.

`help_key_for` returns the family's pattern itself rather than the entry.
`Refinement.parameters()` puts that pattern on every row as `ParameterRow.help_key`.
A row carries the key and not the entry because an entry describes a family, so a copy on each row would repeat the same paragraph once per atom.

```python
import rietx as rx

print(rx.help_key_for("phases.0.atoms.3.biso"))
print(rx.help_key_for("phases.0.atoms.3.nonsense"))
```

```text
phases.*.atoms.*.biso
None
```

`help_registry` returns the whole corpus as data that converts to JSON, and the GUI's `GET /api/help` serves it.
Each object in its `parameters` list names every pattern that reaches it, so a `help_key` is looked up there.

```python
import rietx as rx

registry = rx.help_registry()
print(sorted(registry))
print(registry["peak_flags"]["axial_tail"]["title"])
```

```text
['diagnostics', 'instrument_fields', 'parameters', 'peak_flags', 'peak_origins', 'plans', 'reader_options', 'result_fields', 'search_fields', 'stage_fields']
Possibly a stronger line's axial tail
```

`rietx.help.explain` looks up a diagnostic code or a result field, as [Result fields](result-fields.md) shows.

## Entry fields

Each entry is a `HelpEntry` with seven fields.

`HelpEntry.title`
: The name in words.

`HelpEntry.description`
: What the quantity is, and what moves it.

`HelpEntry.unit`
: The unit, or `None` where the quantity has no unit.
  `tests/test_help.py` pins it against the schema's own `Parameter.unit`.

`HelpEntry.default`
: The value the schema starts from, as a string, or `None` where there is none.
  A lattice parameter has no default because it arrives with the structure.
  The test pins this against the schema too.

`HelpEntry.typical`
: A range to check a refined number against.
  It is guidance and not a bound, and nothing in the package reads it.
  The ranges come from McCusker et al. (1999) {cite}`mccusker1999` and from this repository's own reference datasets, and a specimen outside one is not thereby wrong.

`HelpEntry.anchor`
: The page and heading of this manual that carry the explanation, as `page.html#heading-id`, such as `theory/corrections.html#surface-roughness`.
  It is relative to the manual of the running version, `rietx._about.docs_base`, which is what the GUI joins it to.
  `tests/test_help.py` checks each one against this manual's built HTML.

`HelpEntry.label`
: The short form a chip carries where the name would not read: `at bound` for `position_at_bound`.
  Only the `peak_flags` and `peak_origins` entries carry one, and every entry there must.
  It is `None` elsewhere, where no chip is drawn.

```{include} ../_generated/settings.md
```
