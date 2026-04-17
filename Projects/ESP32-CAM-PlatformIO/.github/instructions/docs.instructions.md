---
applyTo: "docs/**/*"
---

# Documentation Instructions

These instructions apply to all documentation in `docs/`.

## Structure

```
docs/
├── wiring/            # wiring diagrams and connection tables
├── guides/            # how-to guides and tutorials
├── api/               # library API reference
├── releases/          # release notes and changelogs
└── manufacturing/     # flash instructions, BOM, assembly notes
```

## Formatting Standards

- Use Markdown for all documentation.
- Use tables for pin-to-pin wiring connections. Columns: Signal Name | Source Pin | Destination Pin | Notes.
- Use fenced code blocks with language tags for all code snippets (```cpp, ```bash, ```ini).
- Use numbered lists for step-by-step procedures.
- Use headings hierarchically: `#` for page title, `##` for major sections, `###` for subsections.

## Wiring Tables

- Always reference the board pin map file as the source of truth. Example: "Pin assignments from `boards/esp32-devkit/pins.h`."
- Include both GPIO number and silkscreen label when they differ.
- Note voltage levels and required pull-up/pull-down resistors.
- For complex wiring, include an ASCII diagram or reference an image in `docs/wiring/images/`.

## Code Examples in Docs

- Every code example must compile. Treat examples as tests.
- Include the target board and any required library dependencies.
- Keep examples minimal — show one concept, not a complete application.
- Include expected serial output as a comment block at the end.

## Release Notes

- Follow Keep a Changelog format: Added, Changed, Deprecated, Removed, Fixed, Security.
- Include binary size delta for firmware changes (flash and RAM).
- List affected board targets.
- Include flashing instructions if the update process differs from standard.

## API Documentation

- Document every public function/method with: brief description, parameters, return value, example usage.
- Note any functions that are not interrupt-safe or not reentrant.
- Document units for all numeric parameters and return values (ms, µs, mA, °C, raw ADC counts, etc.).

## Anti-Patterns

- Do not document features that don't exist yet.
- Do not leave placeholder text (`TODO`, `TBD`, `Lorem ipsum`) in committed docs.
- Do not duplicate information — link to the source of truth instead.
- Do not use screenshots of text. Use actual text.
