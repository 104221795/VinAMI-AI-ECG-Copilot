# System Context

## Purpose

VinAMI ACS Operating System coordinates the review workflow for a suspected ACS case. It records evidence, creates review work, and makes every decision traceable. It is a research and engineering MVP, not a medical device, AMI rule-out product, guideline engine, or autonomous activation system.

Every UI surface that exposes a demo rule must display: **"Demonstration rule - not for clinical use."**

```mermaid
C4Context
title VinAMI ACS Operating System - System Context
Person(nurse, "ED nurse", "Registers encounters, records observations, uploads evidence")
Person(physician, "Physician", "Reviews evidence and confirms consequential decisions")
Person(cardiologist, "Cardiologist", "Receives review tasks; may record a review decision")
System(acs, "VinAMI ACS Operating System", "Research MVP for suspected-ACS case workflow, evidence, tasks, alerts, timeline and audit")
System_Ext(ecgResearch, "VinStroke-ECG research prototype", "Independent PTB-XL/ConvNeXtV2 research artifact; optional replaceable AI adapter only")
System_Ext(lis, "Laboratory information system", "Future troponin result source; mocked in MVP")
System_Ext(ehr, "EHR/registration system", "Future patient and encounter source; manually entered in MVP")
System_Ext(idp, "Identity provider", "Future authentication source; placeholder actor identity in MVP")
Rel(nurse, acs, "Uses case workflow", "HTTPS")
Rel(physician, acs, "Reviews and confirms", "HTTPS")
Rel(cardiologist, acs, "Receives and completes review work", "HTTPS")
Rel(acs, ecgResearch, "Optionally requests normalized ECG analysis", "Adapter contract")
Rel(lis, acs, "Will provide troponin results", "Future integration")
Rel(ehr, acs, "Will provide patient/encounter references", "Future integration")
Rel(idp, acs, "Will authenticate actors", "Future integration")
```

## System Boundaries

- VinAMI owns the ACS case, workflow, ruleset version, task, alert, timeline, audit event, model provenance, and references to clinical evidence.
- VinAMI does not claim diagnostic truth, rule out AMI, activate a cath lab, interpret ESC/AHA guidelines, or replace a clinician.
- Patient identity and laboratory/EHR integration are manually entered or mocked in the MVP. They are designed as adapters, not copied as external source-of-truth data.
- VinStroke-ECG is preserved as an independent research prototype. It may provide a normalized result, but has no authority to alter ACS workflow by itself.

