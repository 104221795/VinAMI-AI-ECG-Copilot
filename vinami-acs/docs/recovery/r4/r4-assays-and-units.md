# R4 Assays and Units

## Demonstration catalog

| Code               | Category | Analyte            | Canonical unit | Reference limit |
| ------------------ | -------- | ------------------ | -------------- | --------------- |
| `DEMO-HS-CTNI-01`  | hs-cTnI  | cardiac troponin I | `ng/L`         | Not seeded      |
| `DEMO-HS-CTNT-01`  | hs-cTnT  | cardiac troponin T | `ng/L`         | Not seeded      |
| `UNKNOWN-TROPONIN` | unknown  | unknown troponin   | unavailable    | Not seeded      |

The named assays are synthetic metadata for engineering demonstrations. They do not represent a manufacturer-validated assay configuration.

## Explicit conversion policy

Policy version: `troponin-unit-conversion-v1`.

| Original | Canonical | Factor | Basis                                           |
| -------- | --------- | -----: | ----------------------------------------------- |
| `ng/L`   | `ng/L`    |      1 | Identity                                        |
| `pg/mL`  | `ng/L`    |      1 | `1 pg/mL = 1 ng/L` by SI mass/volume conversion |
| `ng/mL`  | `ng/L`    |   1000 | `1 L = 1000 mL`                                 |

All other conversions are rejected. Units are case-sensitive canonical strings. No unit is guessed, no unknown assay is normalized, and no reference limit is inferred. Reference-limit value, unit and source are retained independently from normalized measurement data.

## Delta compatibility

A pair is technically compatible only when analyte, assay definition and normalized unit match. The system reports numerical absolute and relative change with `troponin-delta-v1`. It gives no diagnostic meaning to the result. Relative change is absent when baseline is zero or unavailable.
