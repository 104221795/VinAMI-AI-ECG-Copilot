ROLE

You are a Principal Software Architect, Principal AI Engineer, Clinical Informatics Architect, and Staff Full-stack Engineer.

You have experience building FDA-grade Software as a Medical Device (SaMD), scalable hospital workflow platforms, and AI-powered clinical operating systems similar in architecture to Viz.ai.

You understand:

Clinical workflow
Emergency medicine
Acute Coronary Syndrome (ACS)
STEMI / NSTEMI pathways
ESC 2023 Guidelines
AHA Guidelines
Event-driven architecture
Domain-driven design (DDD)
Clean Architecture
Hexagonal Architecture
CQRS
SOLID
FastAPI
Python
PyTorch
Streamlit
PostgreSQL
Docker
Redis
Celery
SQLAlchemy
Alembic
OpenTelemetry
MLflow
Prometheus
Grafana

Your goal is NOT to build an ECG classifier.

Your goal is to build a Clinical Operating System for Acute Coronary Syndrome.

PRODUCT

Product name

VinAMI ACS Operating System

Vision

Become the "Viz.ai for Acute Coronary Syndrome"

AI is NOT the product.

Clinical Workflow is the product.

ECG AI is only one module.

The system must support future expansion to

Stroke

Heart Failure

Pulmonary Embolism

Sepsis

Multimodal AI

without redesign.

ARCHITECTURE PRINCIPLES

Use

Domain Driven Design

Hexagonal Architecture

Event Driven Architecture

Clean Architecture

CQRS where appropriate

Repository Pattern

Dependency Injection

Plugin architecture

Every module must be independently replaceable.

Never tightly couple AI with workflow.

AI must only expose prediction APIs.

Workflow consumes AI outputs.

SYSTEM LAYERS

Implement these ten layers.

Layer 1

Hospital Integration

Patient

Encounter

Clinical Case

FHIR-ready domain model

HL7 adapter interface

Mock adapter for MVP

Layer 2

Intelligent Triage

Chief complaint

Vitals

Symptoms

Rule-based MVP

Future AI-ready

Layer 3

ECG Intelligence

ECG ingestion

Raw waveform

PDF

XML

DICOM ECG

Signal preprocessing

Quality assessment

AI inference interface

Explainability

Model registry

Mock ECG AI for MVP

Later replace with PTB-XL trained model.

Layer 4

Dynamic ECG

Timeline comparison

ECG evolution

Repeat ECG reminder

Lead comparison

Change detection

Rule-based MVP

Layer 5

Troponin Intelligence

Assay database

Abbott

Roche

Siemens

Beckman

0h

1h

2h

3h

delta calculation

ESC algorithms

Timer engine

Reminder engine

No ML.

Layer 6

Clinical Reasoning Engine

Inputs

ECG

Troponin

Symptoms

Vitals

Risk scores

Outputs

STEMI pathway

Very high risk NSTE-ACS

High risk

Observe

Rule-out candidate

Use transparent rules.

Future AI plugin.

Layer 7

Clinical Workflow Orchestrator

Task engine

Cath lab activation

Repeat ECG

Cardiology consult

Transfer PCI

Notifications

Escalation

Workflow state machine

Layer 8

Clinical Command Dashboard

Streamlit

Real-time

Patient queue

Timers

Priority

Alerts

Timeline

Explainability

Audit

Layer 9

Safety Layer

Never allow ECG alone to rule out AMI.

Always require physician confirmation.

Detect conflicts.

Generate safety alerts.

Human in the loop.

Layer 10

Learning Platform

Store

Timeline

Predictions

Decisions

Outcomes

Model version

Future ML dataset generation.

DATABASE

Implement PostgreSQL.

Use SQLAlchemy.

Alembic.

Tables include

Patient

Encounter

ClinicalCase

Symptoms

Vitals

ECGStudy

ECGAIResult

ECGFinding

LabOrder

LabResult

TroponinTimeline

RiskScore

ClinicalPathway

Task

Alert

ClinicalUser

ClinicalTeam

AuditLog

TimelineEvent

Outcome

ModelRegistry

Use UUID everywhere.

Use created_at

updated_at

Soft delete where appropriate.

EVENT SYSTEM

Everything must generate events.

Examples

PatientArrived

ECGUploaded

AIStarted

AICompleted

TroponinOrdered

TroponinCollected

RepeatECGDue

CathLabActivated

TransferRequested

Discharged

All events stored.

Replayable.

AI

Use plugin architecture.

Never embed PyTorch inside business logic.

AI Provider interface

predict()

explain()

health()

Mock implementation

Random probabilities

Demo heatmap

Later replace by

PTB-XL

Torch

ONNX

without changing workflow.

DATASETS

Design interfaces for

PTB-XL

PTB Diagnostic

Georgia

Chapman

CODE-15%

Do NOT download datasets.

Create adapters.

API

Use FastAPI.

Swagger.

REST.

Versioned APIs.

Authentication placeholder.

Health endpoint.

Metrics endpoint.

STREAMLIT

Modern dashboard.

Dark theme.

Patient queue.

ACS pathway.

ECG viewer.

Troponin timeline.

Alerts.

Workflow.

Audit.

Model version.

Explainability.

Timeline.

OBSERVABILITY

Logging

Tracing

Metrics

Prometheus

OpenTelemetry

Structured logs.

TESTING

pytest

Unit tests

Integration tests

Workflow tests

Mock AI tests

DEVOPS

Docker

docker-compose

Makefile

pre-commit

GitHub Actions

.env.example

Seed database

Demo data

DEMO

Seed five realistic ACS patients.

STEMI

NSTEMI

Rule-out

Posterior MI

Troponin rising

The dashboard must work immediately.

CODE QUALITY

Use Python typing.

Pydantic.

Docstrings.

No TODOs.

No placeholder files.

No pseudo-code.

Everything runnable.

Production-grade folder structure.

OUTPUT

Generate the COMPLETE repository.

Every file.

Every folder.

Every API.

Every model.

Every schema.

Every Docker configuration.

Every migration.

Every test.

Every demo data.

Everything must run with

docker compose up --build

The project should represent an MVP that can later evolve into an FDA-grade Clinical Operating System comparable in architecture (not functionality claims) to leading workflow platforms.

Tuy nhiên...

Nếu mục tiêu của bạn là thực sự code được bằng Codex, thì prompt trên vẫn quá lớn.

Một repository như vậy sẽ khoảng 80.000–150.000 dòng code. Không một LLM hiện nay có thể sinh đúng toàn bộ trong một lần.

Cách mà OpenAI, Anthropic hay Microsoft thường làm là chia thành các milestone.

Ví dụ:

Prompt 1: Scaffold toàn bộ kiến trúc (folder, DDD, database, Docker, FastAPI).
Prompt 2: Hoàn thiện Domain + PostgreSQL + Alembic.
Prompt 3: Workflow Engine + Event Bus.
Prompt 4: AI Provider + ECG module.
Prompt 5: Streamlit Dashboard.
Prompt 6: Test, CI/CD và observability.

Đây là cách có tỷ lệ thành công rất cao và cho ra code chất lượng hơn nhiều so với một prompt khổng lồ.

Nếu mình dẫn dắt dự án này, mình sẽ không dùng 1 prompt mà sẽ dùng khoảng 15–20 prompt có cấu trúc, mỗi prompt tương ứng với một sprint kỹ thuật. Kết quả sẽ gần với một sản phẩm production-ready hơn là một demo do AI sinh ra trong một lần.

được hãy cho tôi từng prompt một và mục đích của từng prompt yêu cầu thật là advanced, professional, tốt nhất có thể 

Mình nghĩ đây mới là hướng đi đúng.

Nếu bạn muốn xây VinAMI ACS Operating System thật sự, thì đừng dùng Codex như "code generator".

Hãy dùng nó như một Senior Engineer trong team.

Nếu mình là CTO của VinBrain/Vingroup

Mình sẽ chia toàn bộ project thành 18 Sprint Prompts.

Đây gần như là cách các Big Tech triển khai.

Sprint 0

Architecture

↓

Sprint 1

Repository

↓

Sprint 2

Database

↓

Sprint 3

Domain

↓

Sprint 4

Workflow Engine

↓

Sprint 5

Event Bus

↓

Sprint 6

API

↓

Sprint 7

AI Engine

↓

Sprint 8

Clinical Rules

↓

Sprint 9

Dashboard

↓

Sprint 10

Timeline

↓

Sprint 11

Notification

↓

Sprint 12

Observability

↓

Sprint 13

Security

↓

Sprint 14

Testing

↓

Sprint 15

Docker

↓

Sprint 16

Seed Data

↓

Sprint 17

Release Candidate

Đây chính xác là roadmap của một đội Staff Engineer.

SPRINT 0
System Architecture

Mục tiêu

Không viết code nhiều.

Chỉ thiết kế.

Codex phải suy nghĩ như Principal Architect.

Deliverable

C4 Diagram
DDD
Bounded Context
Service Boundary
Event Flow
Folder Structure
Dependency Graph
Data Flow
AI Flow
Sequence Diagram
Deployment Diagram
ADR (Architecture Decision Records)

Đây là sprint quan trọng nhất.

SPRINT 1
Repository Scaffold

Mục tiêu

Sinh toàn bộ project.

vinami-acs/

backend/

frontend/

ai/

infra/

tests/

docs/

scripts/

Docker

Poetry

Pre-commit

Makefile

Github Action

Không viết business.

SPRINT 2
Database

Đây là sprint lớn.

Codex sinh

ERD

SQLAlchemy

Alembic

Indexes

FK

UUID

Soft delete

Optimistic Locking

Audit

Migration

Seed

Không viết API.

SPRINT 3
Domain Layer

Viết

Entities

Aggregates

Repositories

Value Objects

Factories

Domain Events

Policies

Specifications

DDD thật.

Không CRUD.

SPRINT 4
Clinical Workflow Engine

Đây là trái tim.

Codex phải viết

State Machine

Workflow

Transitions

Command Pattern

Task Engine

Escalation

Retry

Compensation

Không dùng if else.

SPRINT 5
Event Bus

Đây là Viz.ai style.

PatientArrived

↓

ECGUploaded

↓

AICompleted

↓

TroponinCollected

↓

CathActivated

Codex phải viết

Publish

Subscribe

Replay

Persistence

Event Versioning

SPRINT 6
FastAPI

Toàn bộ REST.

Versioning.

OpenAPI.

DTO.

Validation.

Error Handling.

Middleware.

Dependency Injection.

Không business.

SPRINT 7
AI Framework

Quan trọng.

Không viết model.

Viết

AI Plugin

Provider

Registry

ONNX

Torch

TensorRT

OpenVINO

Health Check

Explainability API

Inference Queue

GPU abstraction

Mock provider

Sau này thay model không sửa backend.

SPRINT 8
Clinical Intelligence

Đây là guideline.

ESC 2023.

Rule Engine.

Decision Tree.

Checklist.

Troponin.

ACS pathway.

Không ML.

SPRINT 9
Dashboard

Streamlit.

Modern UI.

Timeline.

Patient Queue.

Heatmap.

Troponin.

Workflow.

Alerts.

Audit.

SPRINT 10
Timeline Engine

Đây là module rất mạnh.

Event Sourcing.

Replay.

Undo.

Time Travel.

Patient Journey.

Door-to-balloon.

Door-to-ECG.

SPRINT 11
Notification

SMS

Email

Teams

Slack

Push

Webhook

Retry

Priority Queue

SPRINT 12
Observability

Prometheus

Grafana

OpenTelemetry

Tracing

Structured Logging

Business Metrics

Clinical KPI

SPRINT 13
Security

JWT

RBAC

ABAC

Audit

Encryption

Secrets

Rate Limit

HIPAA-ready

FHIR Security

SPRINT 14
Testing

pytest

Contract Test

Integration Test

Workflow Test

AI Test

Mutation Test

Benchmark

Coverage

SPRINT 15
DevOps

Docker

Compose

Helm

K8s

CI/CD

Github Actions

Release

Version

SPRINT 16
Demo

5 bệnh nhân

STEMI

NSTEMI

Posterior

Rule Out

Shock

Timeline đầy đủ.

SPRINT 17
Production Hardening

Caching

Performance

Indexes

Background Jobs

Retry

Graceful Shutdown

Health Check

Scaling

Điều quan trọng hơn

Nếu bạn để ý.

Mình chưa hề nói "train AI".

Đó chính là khác biệt giữa

AI Project

và

Clinical Platform.

Nếu là Viz.ai

Khối lượng code sẽ khoảng

Frontend

20%

Backend

35%

Workflow

20%

Infrastructure

15%

AI

10%

AI chỉ khoảng

10%

toàn bộ codebase.

Đây là điều mình khuyên bạn nên làm

Nếu mục tiêu của bạn là một sản phẩm có thể trình diễn với VinBrain hoặc triển khai thử nghiệm trong bệnh viện, mình sẽ không dừng ở 18 sprint.

Mình sẽ chia thành khoảng 35 prompt chuyên sâu, tương ứng với các epic của một dự án enterprise:

Foundation & Architecture
Platform Core
Clinical Domain
AI Platform
Workflow Engine
Clinical Decision Support
Dashboard & UX
Infrastructure & DevOps
Quality Assurance
Production Readiness

Mỗi prompt sẽ dài khoảng 1.500–3.000 từ, được viết theo chuẩn Staff Engineer/Principal Engineer, với:

Objective (mục tiêu kỹ thuật)
Context (bối cảnh hệ thống)
Constraints (ràng buộc)
Acceptance Criteria (tiêu chí hoàn thành)
Non-functional Requirements (hiệu năng, bảo mật, khả năng mở rộng)
Deliverables (mã nguồn, tài liệu, test)
Coding Standards
Architectural Decisions
Integration Contracts

Đó là mức chi tiết mà các nhóm kỹ thuật lớn thường sử dụng để AI hoặc kỹ sư có thể triển khai nhất quán mà không phải đoán ý người thiết kế.

Theo mình, đây sẽ là một "AI Engineering Playbook" hoàn chỉnh cho VinAMI, chứ không chỉ là một tập hợp prompt rời rạc. Đây cũng là cách có khả năng tạo ra một MVP chất lượng cao và có thể phát triển thành sản phẩm thực sự.