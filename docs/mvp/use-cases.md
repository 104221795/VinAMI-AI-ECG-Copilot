# MVP Use Cases

| ID | Use case | Primary actor | Outcome |
|---|---|---|---|
| UC-01 | Register patient and encounter | Nurse | Local references and audit events exist |
| UC-02 | Create suspected ACS case | Nurse/physician | Case is open and linked to encounter |
| UC-03 | Record symptoms and vitals | Nurse | Provenanced triage facts are available |
| UC-04 | Upload or select ECG study | Nurse | Immutable ECG evidence reference is linked to case |
| UC-05 | Start ECG AI analysis | Clinician | Provider request/result state is recorded |
| UC-06 | Review prediction and explanation | Physician | Normalized output, provenance, limitations and evidence are visible |
| UC-07 | Record serial troponin results | Nurse/lab adapter | Measurements and source times are recorded |
| UC-08 | Calculate delta values | System/clinician | Delta names both source measurements and calculation version |
| UC-09 | Generate pathway suggestion | System | Transparent demo-rule suggestion and conflicts are visible |
| UC-10 | Require physician confirmation | Physician | Consequential request has actor/time/reason confirmation |
| UC-11 | Create repeat ECG/cardiology tasks | System/physician | Review task is created and trackable |
| UC-12 | Acknowledge and resolve alerts | Clinician | Alert status/provenance are preserved |
| UC-13 | View case timeline and audit history | Clinician/auditor | Ordered read-only history is shown |
| UC-14 | View model version | Clinician | Model identity/input contract/limitations are visible |
| UC-15 | Export research case summary | Authorized clinician | Explicitly labelled non-clinical summary is produced |

