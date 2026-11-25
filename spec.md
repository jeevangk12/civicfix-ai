CivicFix AI --- Product & Engineering Specification

Document: spec.md
Version: 1.0.0
Status: Baseline specification for implementation
Project type: AI-powered civic issue reporting and resolution
platform
Initial deployment goal: Controlled real-world pilot with
participating civic stakeholders
Primary users: Citizens, authority staff, administrators

1. Product overview

CivicFix AI is a web platform through which citizens can report civic
infrastructure and sanitation problems, follow their progress, and view
public issue information on a map. AI assists the workflow by
classifying complaints, summarizing them, recommending a priority and
responsible department, and identifying potentially similar complaints.

Authority staff use a secure workspace to review, assign, update, and
resolve complaints. Administrators manage accounts, departments, service
areas, and platform configuration. The system maintains an auditable
history of important actions.

CivicFix AI is intended to support a real-world pilot. The first
release must therefore be safe to operate with real users and real
location data, while remaining realistic for an individual student
developer to build. A pilot does not imply an official government
partnership, government endorsement, or guaranteed service-level
commitment. The project must clearly identify the participating
organization and the platform's status, and must not represent itself as
an official municipal service unless written authorization has been
obtained.

1.1 Product vision

Make civic issue reporting more structured, transparent, location-aware,
and actionable by combining citizen reports, human authority workflows,
and responsible AI assistance.

1.2 Problem statement

Citizens may find it difficult to identify the correct department,
submit complete reports, or understand what happens after reporting.
Authorities may receive incomplete or duplicate reports through
disconnected channels and may lack a shared view of issue locations,
priorities, and progress.

CivicFix AI provides one workflow for reporting, triage, assignment,
communication, and resolution tracking.

1.3 Goals

Let a citizen submit a civic issue with a description, category
(optional), location, and optional evidence image.

Make reports discoverable on a public map without exposing personal
or sensitive information.

Use Gemini to provide structured, explainable recommendations for
category, summary, priority, and department.

Detect and display potential duplicate reports for human review;
never silently merge or discard a report.

Give authorized staff tools to review, assign, update, and resolve
complaints.

Keep a timestamped history of status changes and staff actions.

Notify relevant users through in-app notifications.

Provide administrators with operational dashboards and basic
analytics.

Support a controlled real-world pilot with explicit onboarding,
access control, privacy notices, and operational safeguards.

1.4 Non-goals for MVP

Replacing official government complaint channels.

Claiming that a government department has accepted or acted on a
complaint unless an authorized staff member records that action.

Automatically dispatching field workers or allocating government
budgets.

Automatically merging, rejecting, or closing complaints using AI.

Predicting exact repair dates or guaranteeing resolution times.

Integrating with government ERP, GIS, payment, identity, or
grievance systems.

Native Android/iOS applications.

Voice calls, WhatsApp bot, SMS, and email notifications.

Public comments, public user profiles, citizen-to-citizen messaging,
or public display of reporter identities.

Advanced predictive analytics or automated resource allocation.

2. Confirmed product decisions

Decision                            Confirmed requirement

Authority model                     Real-world pilot with participating
authority/stakeholder accounts

Public visibility                   Public complaint map

Duplicate handling                  AI/system suggests possible
duplicates; a human reviews them

Notifications                       In-app notifications in MVP

Frontend                            React, Vite, TypeScript, CSS3

Backend                             Python, FastAPI

Database                            PostgreSQL

AI provider                         Google Gemini API

Authentication                      JWT-based authentication

Image storage                       Cloudinary

Maps                                Leaflet + OpenStreetMap

Charts                              Chart.js

Deployment                          Vercel frontend, Render backend;
managed PostgreSQL

2.1 Pilot operating principle

The system must support two kinds of accounts: - Platform
administrator: configures the installation and provisions authority
accounts. - Authority staff: belongs to a participating organization
and one or more departments/service areas.

The first pilot must be configured for a named pilot area and
participating organization. Do not create public self-registration for
authority staff. An administrator invites or provisions staff accounts.
Citizens may self-register.

Before a public pilot, the project owner must obtain permission from the
relevant organization, confirm who is authorized to view and act on
reports, publish a privacy notice and terms, and define an
escalation/contact route. If permission is not obtained, run the
application as a clearly labelled demonstration/pilot simulation rather
than implying official status.

3. Users, roles, and permissions

3.1 Roles

Citizen

Register, log in, log out, and manage limited profile information.

Submit a complaint and optional images.

Choose a point on the map or use browser geolocation with explicit
permission.

View own complaint details and status history.

View the public map and public-safe complaint summaries.

Receive in-app notifications.

Mark a possible duplicate as relevant, if that feature is enabled
later; not required for MVP.

Submit feedback after a complaint is resolved.

Authority staff

Log in using an administrator-provisioned account.

View complaints within permitted organization, department, and
service-area scope.

Review AI recommendations and possible duplicates.

Confirm or change category, priority, and department.

Assign complaints to authorized staff.

Update status and add public-safe progress notes.

Add internal-only notes where permitted.

Upload resolution evidence.

View relevant complaint history and operational dashboard.

Platform administrator

Manage users, authority organizations, departments, and staff
memberships.

Configure pilot area, categories, priority rules, and department
mappings.

View and manage all complaints within the installation.

Review audit events and AI failure records.

Suspend/reactivate accounts.

Configure public-map privacy and feature flags.

Cannot erase audit history through normal application workflows.

3.2 Authorization rules

Enforce authorization on the backend for every protected endpoint.
Hiding UI controls is not authorization.

Citizens can read and update only their own profile and read their
own private complaint details.

Public users can read only explicitly public-safe complaint fields.

Staff can access only complaints in their authorized
organization/department/service-area scope.

Admin permissions are separate from staff permissions.

Staff account creation/invitation is admin-only.

Every staff status change, assignment, priority override, department
change, rejection, and resolution action must create an audit event.

Use deny-by-default authorization.

Prevent insecure direct object references by checking
ownership/scope for every resource ID.

4. Civic issue taxonomy and business rules

4.1 Initial categories

Road damage / pothole

Garbage accumulation / waste collection

Streetlight failure

Water leakage / water supply

Drainage / sewage / blocked drain

Footpath / pedestrian infrastructure

Public property damage

Traffic signal / road signage

Tree obstruction / fallen tree

Other / needs review

Categories and department mappings must be stored/configurable, not
hard-coded only in frontend code.

4.2 Priority levels

Critical: immediate apparent threat to life or major public
safety; requires urgent human review.

High: significant safety, access, sanitation, or infrastructure
impact.

Medium: meaningful civic inconvenience or localized service
disruption.

Low: minor issue with limited immediate impact.

AI provides a recommendation, not an authoritative decision. Staff may
override it and must provide a reason. The interface must label AI
priority as "AI recommended" until a human confirms it.

Do not promise response or resolution times in the MVP. If a
participating authority later defines service targets, configure them
explicitly and label them as pilot targets, not guarantees.

4.3 Complaint statuses

Use these canonical statuses:

SUBMITTED

UNDER_REVIEW

ASSIGNED

IN_PROGRESS

RESOLVED

CLOSED

REJECTED

Allowed transitions:

Current status   Allowed next status

SUBMITTED        UNDER_REVIEW, REJECTED
UNDER_REVIEW     ASSIGNED, REJECTED
ASSIGNED         IN_PROGRESS, UNDER_REVIEW
IN_PROGRESS      RESOLVED, ASSIGNED
RESOLVED         CLOSED, IN_PROGRESS
CLOSED           none in MVP
REJECTED         none in MVP

Only authorized staff may change a complaint's status. Rejection
requires a reason. Moving from RESOLVED back to IN_PROGRESS requires
a reason. A citizen may request reconsideration through a future
feature; they cannot directly change status.

4.4 Complaint data and validation

Required: - Title (5--120 characters). - Description (20--5,000
characters). - Location latitude and longitude. - Category may be
omitted or selected as a citizen hint. - Location description/address is
optional but encouraged.

Optional: - One or more images, subject to configured limits. - Nearby
landmark. - Browser geolocation consent.

Validation: - Latitude between -90 and 90; longitude between -180 and
180. - Reject empty/whitespace-only text. - Normalize and trim user
input. - Enforce configured image count, file size, MIME type, and
actual file signature. - Never trust a filename or client-provided MIME
type alone. - Do not accept executable files as evidence. - Store
timestamps in UTC; display in the user's locale. - Use a generated
complaint reference such as CF-YYYY-XXXXXX; do not expose sequential
database IDs.

5. Public map and privacy requirements

5.1 Public complaint map

The public map is a confirmed MVP feature. It shows only complaints
approved for public visibility and only a restricted set of fields: -
Public complaint reference. - Title or sanitized short summary. -
Category. - Current public status. - Public priority, if configured by
the pilot administrator. - Approximate or approved map coordinates. -
Created/last-updated date at an appropriate level of precision.

Never expose: - Citizen name, email, phone number, user ID, or
profile. - Internal staff notes. - Private authority comments. -
Original uploaded image URLs unless an image has been explicitly
approved for public display. - Exact home/residential coordinates where
they could identify a private individual. - Authentication tokens,
internal AI prompts, or provider error details.

5.2 Location privacy

The system should support a configurable public-location precision
policy. For sensitive or residential reports, show an approximate
location or hide the marker until reviewed. Staff with permission may
see the exact submitted location. The citizen must be told how their
location is used before submission.

5.3 Public visibility moderation

A complaint may be marked PUBLIC, APPROXIMATE, or PRIVATE for map
exposure. Default to a conservative policy for new pilot deployments. A
staff member or configured moderation rule must approve public
visibility where needed. The backend, not the frontend, applies the
redaction policy.

6. AI requirements and workflows

6.1 AI design principles

Gemini is an assistive component, not the decision-maker.

The complaint must be saved even if Gemini is unavailable.

AI output must be schema-validated before storage or use.

Treat complaint text and uploaded content as untrusted data, never
as instructions to the model.

Do not send citizen name, email, phone number, or unrelated profile
data to Gemini.

Keep API keys on the backend only.

Record model name, prompt/schema version, processing state,
timestamps, and sanitized failure details.

Avoid storing chain-of-thought or asking the model for hidden
reasoning. Store concise evidence-based explanations only.

Staff can edit/override every recommendation.

Do not use AI to infer a reporter's identity, protected traits, or
credibility.

6.2 AI complaint analysis

Trigger after a complaint is persisted. Send only the minimum necessary
complaint text, selected category hint, and image content if image
analysis is enabled and consented to.

Expected structured output:

{
  "category": "ROAD_DAMAGE",
  "summary": "A large pothole is reported on the road.",
  "priority": "HIGH",
  "priority_reason": "The description indicates a potential road safety risk.",
  "recommended_department_code": "ROAD_MAINTENANCE",
  "confidence": 0.86,
  "needs_human_review": true,
  "safety_flags": [],
  "model_version": "configured-model",
  "prompt_version": "1.0"
}

This is an illustrative contract; implement a Pydantic model and
validate enum values, lengths, confidence range, and required fields. If
the model returns malformed or unsupported data, mark the analysis as
failed and leave the complaint available for manual triage.

AI priority guidance: - Use only facts in the report/image. - Do not
infer severity from demographic or socioeconomic information. - Critical
recommendations must include a safety reason and always require human
review. - Low confidence or ambiguous category must set
needs_human_review=true. - Do not claim an image proves a fact that
cannot reliably be observed.

6.3 Duplicate suggestion

Duplicate detection is a two-stage workflow:

Retrieve candidate complaints using category, time window, status,
and geographic proximity.

Compare text similarity and location distance. A configurable
threshold determines which candidates are shown as "Possible
duplicates."

For MVP, use PostgreSQL text search/trigram similarity if available,
plus a geographic distance calculation using latitude/longitude. PostGIS
may be added if supported by the chosen database service. Gemini may
optionally summarize why two reports appear similar, but must not be the
only duplicate detector.

Store: - Source complaint. - Candidate complaint. - Similarity score. -
Distance in meters (when calculable). - Detection method/version. -
Review status: PENDING, CONFIRMED_DUPLICATE, NOT_DUPLICATE. -
Reviewer and review timestamp.

Never merge or delete automatically. Staff can mark a candidate as a
confirmed duplicate. Preserve both original reports and their history.
If confirmed, link the reports and show the citizen a clear explanation
and the primary complaint reference. The original report remains
auditable.

6.4 Department recommendation

Use configurable category-to-department mappings as the deterministic
baseline. Gemini may suggest a department, but the final recommendation
must be checked against active departments configured for the pilot. If
no valid match exists, route to NEEDS_REVIEW or an
administrator-defined triage queue.

6.5 AI failure handling

Set analysis state to PENDING, PROCESSING, SUCCEEDED, or
FAILED.

Use bounded retries with backoff for transient provider errors.

Do not block the citizen's complaint submission on the AI request.

Show "AI analysis pending" or "Manual review required" in the UI.

Log sanitized errors without secrets or personal information.

Provide staff a manual triage path.

Apply provider timeouts and rate limits.

7. Functional requirements

7.1 Authentication and account management

Citizen registration with name, email, and password.

Email uniqueness, normalized case-insensitively.

Secure password hashing using Argon2id.

Login and logout.

Short-lived access JWT and refresh-session mechanism.

Refresh-token rotation and revocation.

Password reset may be deferred if no email provider is configured;
never implement a fake reset flow.

Admin-provisioned authority accounts.

Account active/suspended state.

Role and organization membership checks on the server.

JWT requirements: - Sign with a strong secret from environment
configuration or an asymmetric key pair. - Validate signature, issuer,
audience, expiry, and token type. - Do not store raw refresh tokens;
store a cryptographic hash. - Use secure, HttpOnly, SameSite cookies for
refresh tokens where deployment architecture permits. If access tokens
are stored in memory, document refresh behavior. Avoid localStorage for
long-lived credentials. - Configure CORS to exact allowed frontend
origins in production.

7.2 Citizen complaint reporting

Create a complaint with required text and coordinates.

Upload images through a backend-authorized Cloudinary flow.

Show upload progress and retry behavior.

Save complaint before starting asynchronous AI work.

Return a public reference and current processing state.

Prevent accidental duplicate submissions through an idempotency key
or client-generated submission key.

Allow citizen to view their complaint, updates, and public
visibility state.

Citizen cannot edit a complaint after authority review in MVP; allow
correction only through a defined staff-assisted process.

7.3 Authority complaint management

List complaints in staff scope with pagination and filters.

View full complaint details and authorized evidence.

Review AI analysis and possible duplicates.

Confirm/change category, priority, and department.

Assign to eligible staff.

Transition status according to the transition table.

Add public progress update or internal note with explicit
visibility.

Upload resolution evidence.

Record resolution description.

All significant actions produce an audit event and, where
appropriate, an in-app notification.

7.4 Notifications

MVP supports in-app notifications only.

Notification events: - Complaint submitted (citizen confirmation). -
Complaint status changed. - Complaint assigned (staff recipient). -
Staff requests more information (future; not required). - Complaint
resolved or rejected. - Possible duplicate confirmed (citizen
notification where applicable).

Each notification has recipient, type, title, body, optional resource
link, created time, read time. Do not put sensitive internal notes in
notification text. Support unread count and mark-as-read.

7.5 Feedback

After resolution, a citizen may submit a rating and optional comment.
One feedback record per citizen per complaint. Feedback must be
protected against spam and should not expose the citizen publicly.

7.6 Dashboards and analytics

Citizen dashboard: - Total reports. - Open reports. - Resolved
reports. - Recent reports and statuses.

Staff dashboard: - Assigned/open complaints. - Counts by status and
priority. - Oldest pending items. - Category and area filters.

Admin dashboard: - Total complaints and trend. - Counts by status,
category, priority, department. - Average time to resolution (clearly
define calculation). - AI analysis success/failure counts. - Duplicate
suggestions and review outcomes.

Analytics must respect role and organizational scope. Use server-side
aggregation and pagination; do not download every complaint to the
browser to calculate charts.

8. Technical architecture

8.1 High-level architecture

Citizen / Authority / Admin browser
              |
              v
       React + Vite + TypeScript
              |
       HTTPS REST API (JSON)
              |
              v
        FastAPI application
        |       |        |
        |       |        +---- Gemini API (server-side)
        |       |
        |       +------------- Cloudinary (image storage)
        |
        +---- SQLAlchemy ORM
                    |
                    v
                PostgreSQL

Leaflet/OSM tiles are loaded by the frontend from the configured tile
provider. Chart.js renders dashboard aggregates returned by the API.

8.2 Repository structure

civicfix-ai/
├── spec.md
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docs/
│   ├── architecture.md
│   ├── database-schema.md
│   ├── api-contract.md
│   ├── threat-model.md
│   └── pilot-operations.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── endpoints/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── complaints/
│   │   │   ├── ai/
│   │   │   ├── duplicate_detection/
│   │   │   ├── notifications/
│   │   │   └── storage/
│   │   └── workers/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── api/
└── frontend/
    ├── package.json
    ├── src/
    │   ├── app/
    │   ├── assets/
    │   ├── components/
    │   ├── features/
    │   │   ├── auth/
    │   │   ├── complaints/
    │   │   ├── map/
    │   │   ├── notifications/
    │   │   ├── authority/
    │   │   └── admin/
    │   ├── hooks/
    │   ├── lib/
    │   ├── pages/
    │   ├── routes/
    │   ├── styles/
    │   └── types/
    └── tests/

Use modular service/repository boundaries without overengineering. A
background task mechanism may initially use FastAPI background tasks for
lightweight work, but durable/retriable AI jobs should move to a
queue/worker (for example, Redis-backed worker) before a sustained
pilot. Do not pretend an in-process background task is durable across
server restarts.

8.3 Backend conventions

Python 3.11 or later.

FastAPI with Pydantic v2.

SQLAlchemy 2.x.

Alembic migrations.

PostgreSQL.

Synchronous or asynchronous database access may be selected once and
used consistently; do not mix patterns casually.

All routes under /api/v1.

Pydantic request/response schemas separate from ORM models.

Service layer contains business logic; route handlers remain thin.

Repository layer for non-trivial persistence queries.

Structured logs with request/correlation ID.

Central exception handling and consistent error responses.

OpenAPI docs enabled in development; protect or disable public
interactive docs in production if required by the pilot.

8.4 Frontend conventions

React + Vite + TypeScript.

React Router for routes.

A single typed API client module.

Feature-based component organization.

Reusable form controls and loading/error/empty states.

Route guards improve UX but backend authorization remains
authoritative.

Use environment variables only for public frontend configuration;
never put Gemini, database, or Cloudinary secrets in Vite variables.

Responsive design and keyboard-accessible controls.

Validate forms on client for UX and on server for security.

9. Database schema

Use UUID primary keys for externally referenced entities. Use
timezone-aware timestamps stored in UTC. Add created_at and
updated_at where appropriate. Use database constraints for uniqueness
and valid values.

9.1 users

id UUID PK

full_name VARCHAR(120) NOT NULL

email VARCHAR(255) NOT NULL UNIQUE (normalized)

password_hash TEXT NOT NULL

role ENUM: CITIZEN, STAFF, ADMIN

is_active BOOLEAN NOT NULL DEFAULT true

email_verified_at TIMESTAMPTZ NULL

created_at, updated_at TIMESTAMPTZ NOT NULL

Do not store plaintext passwords or raw refresh tokens.

9.2 organizations

Represents the participating pilot authority or stakeholder
organization.

id UUID PK

name VARCHAR(180) NOT NULL

organization_type VARCHAR(80)

is_active BOOLEAN NOT NULL DEFAULT true

created_at, updated_at

9.3 departments

id UUID PK

organization_id UUID FK -> organizations.id

code VARCHAR(60) NOT NULL

name VARCHAR(150) NOT NULL

description TEXT NULL

is_active BOOLEAN DEFAULT true

UNIQUE (organization_id, code)

9.4 staff_profiles

id UUID PK

user_id UUID FK -> users.id UNIQUE

organization_id UUID FK -> organizations.id

department_id UUID FK -> departments.id NULL

staff_title VARCHAR(120) NULL

created_at, updated_at

If staff may belong to multiple departments, replace the single
department field with a staff_department_memberships join table before
implementing multi-department access.

9.5 service_areas

id UUID PK

organization_id UUID FK -> organizations.id

name VARCHAR(150) NOT NULL

description TEXT NULL

boundary_geojson JSONB NULL (optional MVP boundary)

is_active BOOLEAN DEFAULT true

created_at, updated_at

9.6 categories

id UUID PK

code VARCHAR(60) UNIQUE NOT NULL

name VARCHAR(120) NOT NULL

description TEXT NULL

default_department_id UUID FK -> departments.id NULL

is_active BOOLEAN DEFAULT true

sort_order INTEGER DEFAULT 0

For multi-organization deployments, category-to-department mapping
should be organization-specific through a join table rather than a
single default department.

9.7 complaints

id UUID PK

public_reference VARCHAR(30) UNIQUE NOT NULL

citizen_id UUID FK -> users.id NOT NULL

organization_id UUID FK -> organizations.id NULL until routed

service_area_id UUID FK -> service_areas.id NULL

category_id UUID FK -> categories.id NULL

title VARCHAR(120) NOT NULL

description TEXT NOT NULL

latitude NUMERIC(9,6) NOT NULL

longitude NUMERIC(9,6) NOT NULL

location_label VARCHAR(255) NULL

status complaint-status ENUM NOT NULL DEFAULT SUBMITTED

ai_priority priority ENUM NULL

confirmed_priority priority ENUM NULL

priority_override_reason TEXT NULL

recommended_department_id UUID FK -> departments.id NULL

assigned_department_id UUID FK -> departments.id NULL

assigned_staff_id UUID FK -> users.id NULL

ai_summary TEXT NULL

ai_analysis_status ENUM: PENDING, PROCESSING, SUCCEEDED,
FAILED, SKIPPED

visibility ENUM: PRIVATE, APPROXIMATE, PUBLIC DEFAULT
PRIVATE

public_latitude NUMERIC(9,6) NULL

public_longitude NUMERIC(9,6) NULL

resolution_description TEXT NULL

resolved_at TIMESTAMPTZ NULL

closed_at TIMESTAMPTZ NULL

created_at, updated_at

Indexes: - (citizen_id, created_at DESC) -
(status, created_at DESC) - (assigned_department_id, status) -
(assigned_staff_id, status) - (category_id, created_at DESC) -
location index appropriate to selected geographic approach - unique
index on public_reference

9.8 complaint_images

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

uploaded_by UUID FK -> users.id NOT NULL

cloudinary_public_id VARCHAR(255) NOT NULL

secure_url TEXT NOT NULL

resource_type VARCHAR(30) NOT NULL

mime_type VARCHAR(100) NOT NULL

file_size_bytes BIGINT NOT NULL

image_kind ENUM: REPORT, RESOLUTION

is_public BOOLEAN DEFAULT false

created_at

Keep Cloudinary credentials server-side. Do not assume an uploaded image
is public-safe.

9.9 complaint_updates

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

actor_id UUID FK -> users.id NOT NULL

old_status complaint-status NULL

new_status complaint-status NULL

message TEXT NULL

visibility ENUM: PUBLIC, INTERNAL

created_at

9.10 complaint_assignments

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

department_id UUID FK -> departments.id NOT NULL

assigned_staff_id UUID FK -> users.id NULL

assigned_by UUID FK -> users.id NOT NULL

reason TEXT NULL

assigned_at TIMESTAMPTZ NOT NULL

unassigned_at TIMESTAMPTZ NULL

9.11 ai_analyses

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

provider VARCHAR(40) NOT NULL

model_name VARCHAR(120) NOT NULL

prompt_version VARCHAR(40) NOT NULL

status ENUM: PENDING, PROCESSING, SUCCEEDED, FAILED

suggested_category_id UUID FK -> categories.id NULL

suggested_priority priority ENUM NULL

suggested_department_id UUID FK -> departments.id NULL

summary TEXT NULL

priority_reason TEXT NULL

confidence NUMERIC(4,3) NULL

needs_human_review BOOLEAN DEFAULT true

safety_flags JSONB NOT NULL DEFAULT []

sanitized_error_code VARCHAR(80) NULL

started_at, completed_at, created_at

Do not store secrets, raw provider credentials, or unnecessary personal
data. Retain raw prompts/responses only if there is a documented
operational need, access control, and retention policy; default to
storing validated structured output.

9.12 complaint_duplicates

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

candidate_complaint_id UUID FK -> complaints.id NOT NULL

similarity_score NUMERIC(5,4) NULL

distance_meters NUMERIC(10,2) NULL

detection_method VARCHAR(80) NOT NULL

review_status ENUM: PENDING, CONFIRMED_DUPLICATE,
NOT_DUPLICATE

reviewed_by UUID FK -> users.id NULL

reviewed_at TIMESTAMPTZ NULL

created_at

CHECK complaint IDs differ

UNIQUE (complaint_id, candidate_complaint_id)

Normalize pair ordering or add a canonical pair constraint to avoid
storing the same pair twice in reverse order.

9.13 notifications

id UUID PK

recipient_id UUID FK -> users.id NOT NULL

type VARCHAR(60) NOT NULL

title VARCHAR(160) NOT NULL

body VARCHAR(500) NOT NULL

resource_type VARCHAR(60) NULL

resource_id UUID NULL

read_at TIMESTAMPTZ NULL

created_at

Index (recipient_id, read_at, created_at DESC).

9.14 feedback

id UUID PK

complaint_id UUID FK -> complaints.id NOT NULL

citizen_id UUID FK -> users.id NOT NULL

rating SMALLINT NOT NULL CHECK rating BETWEEN 1 AND 5

comment VARCHAR(1000) NULL

created_at, updated_at

UNIQUE (complaint_id, citizen_id)

9.15 refresh_sessions

id UUID PK

user_id UUID FK -> users.id NOT NULL

token_hash TEXT NOT NULL UNIQUE

expires_at TIMESTAMPTZ NOT NULL

revoked_at TIMESTAMPTZ NULL

created_at TIMESTAMPTZ NOT NULL

replaced_by_session_id UUID FK -> refresh_sessions.id NULL

9.16 audit_logs

id UUID PK

actor_id UUID FK -> users.id NULL

organization_id UUID FK -> organizations.id NULL

action VARCHAR(100) NOT NULL

entity_type VARCHAR(80) NOT NULL

entity_id UUID NULL

metadata JSONB NOT NULL DEFAULT {}

ip_hash VARCHAR(128) NULL (only if justified by pilot policy)

created_at TIMESTAMPTZ NOT NULL

Audit logs are append-only through application permissions. Avoid
recording passwords, tokens, full sensitive request bodies, or
unnecessary personal data.

9.17 Relationship summary

One user can submit many complaints.

One organization has many departments and service areas.

One department can receive many complaints.

One complaint has many images, updates, assignments, AI analyses,
and duplicate candidates.

One user can receive many notifications.

One resolved complaint can have one citizen feedback record per
reporter.

One user can have multiple refresh sessions.

10. API design

Base URL: /api/v1
Content type: application/json, except multipart upload endpoints.
All timestamps: ISO 8601 UTC.
All IDs: UUID strings.
List endpoints: cursor or page-based pagination with a documented
maximum page size.
All protected endpoints require authentication and server-side
role/scope authorization.

10.1 Standard response and error format

Successful single-resource response:

{
  "data": {},
  "meta": {
    "request_id": "request-correlation-id"
  }
}

Paginated response:

{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 0,
    "request_id": "request-correlation-id"
  }
}

Error response:

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": [],
    "request_id": "request-correlation-id"
  }
}

Never return stack traces, SQL errors, secrets, or raw provider
responses to clients.

10.2 Authentication

Method            Endpoint                  Access            Purpose

POST              /auth/register          Public            Register citizen

POST              /auth/login             Public            Authenticate

POST              /auth/refresh           Refresh session   Rotate refresh
session and issue
access token

POST              /auth/logout            Authenticated     Revoke current
refresh session

GET               /auth/me                Authenticated     Current user
profile

POST              /auth/change-password   Authenticated     Change password

10.3 Citizen complaints

Method            Endpoint                                               Access              Purpose

POST              /complaints                                          Citizen             Create complaint

GET               /complaints/mine                                     Citizen             List own
complaints

GET               /complaints/{complaint_id}                           Owner/staff/admin   View authorized
detail

GET               /complaints/{complaint_id}/updates                   Owner/staff/admin   View permitted
history

POST              /complaints/{complaint_id}/images/upload-signature   Owner/staff         Obtain
constrained
upload
authorization if
direct upload is
used

POST              /complaints/{complaint_id}/images                    Owner/staff         Register/verify
uploaded image

POST              /complaints/{complaint_id}/feedback                  Complaint owner     Submit feedback

Prefer a backend-mediated upload or tightly constrained signed upload.
Verify the Cloudinary asset after upload before associating it with a
complaint.

10.4 Public endpoints

Method            Endpoint                                  Access            Purpose

GET               /public/complaints/map                  Public            Public-safe map
markers

GET               /public/complaints/{public_reference}   Public            Public-safe
complaint detail

GET               /public/categories                      Public            Active categories

Public endpoints must use explicit response schemas that cannot
accidentally serialize private ORM fields.

10.5 Authority endpoints

Method            Endpoint                                           Access            Purpose

GET               /authority/dashboard                             Staff             Scoped summary

GET               /authority/complaints                            Staff             Scoped/filterable
queue

POST              /authority/complaints/{id}/review                Staff             Record human review
and triage

PATCH             /authority/complaints/{id}/priority              Staff             Confirm/override
priority

PATCH             /authority/complaints/{id}/category              Staff             Confirm category

POST              /authority/complaints/{id}/assignments           Staff with        Assign
permission        department/staff

POST              /authority/complaints/{id}/status                Staff             Transition status

POST              /authority/complaints/{id}/updates               Staff             Add public/internal
update

GET               /authority/complaints/{id}/duplicates            Staff             View possible
duplicates

POST              /authority/duplicates/{duplicate_id}/review      Staff             Confirm/not
duplicate

10.6 Notifications

Method            Endpoint                        Access            Purpose

GET               /notifications                Authenticated     List own
notifications

GET               /notifications/unread-count   Authenticated     Unread count

PATCH             /notifications/{id}/read      Recipient         Mark read

10.7 Admin endpoints

Method            Endpoint                     Access            Purpose

GET               /admin/dashboard           Admin             Global/pilot
analytics

GET               /admin/users               Admin             List users

POST              /admin/staff               Admin             Provision staff

PATCH             /admin/users/{id}/status   Admin             Activate/suspend
account

GET/POST/PATCH    /admin/organizations       Admin             Manage organizations

GET/POST/PATCH    /admin/departments         Admin             Manage departments

GET/POST/PATCH    /admin/categories          Admin             Manage
categories/mappings

GET/POST/PATCH    /admin/service-areas       Admin             Manage service areas

GET               /admin/audit-logs          Admin             Search audit history

10.8 API behavior requirements

Use explicit Pydantic response models.

Return 201 for successful resource creation, 200 for successful
reads/updates, 204 where a body is unnecessary.

Return 401 for unauthenticated requests, 403 for authenticated
but unauthorized requests, 404 for unavailable/non-visible
resources, 409 for state conflicts, 422 for validation failures,
and 429 for rate limits.

Apply rate limits to registration, login, complaint creation, upload
authorization, and AI-triggering endpoints.

Use transactions for complaint creation plus associated records.

Use idempotency for complaint creation where practical.

Do not expose internal numeric database IDs.

11. Frontend routes and page requirements

Public

/ --- product landing page and pilot disclaimer.

/login --- login.

/register --- citizen registration.

/map --- public-safe complaint map.

/public/complaints/:reference --- public complaint detail.

/privacy --- privacy notice.

/terms --- terms and pilot limitations.

Citizen

/citizen/dashboard

/citizen/complaints/new

/citizen/complaints

/citizen/complaints/:id

/citizen/notifications

/citizen/profile

Authority staff

/authority/dashboard

/authority/complaints

/authority/complaints/:id

/authority/notifications

Administrator

/admin/dashboard

/admin/users

/admin/organizations

/admin/departments

/admin/categories

/admin/service-areas

/admin/complaints

/admin/analytics

/admin/audit-logs

/admin/settings

UI requirements

Responsive layouts for mobile, tablet, and desktop.

Accessible labels, keyboard navigation, focus indicators, and
sufficient contrast.

Clear loading, empty, success, and error states.

Confirm destructive or consequential actions.

Display AI recommendations separately from human-confirmed values.

Show a clear "AI-assisted recommendation --- staff review required"
label.

Use status and priority text as well as color; never rely on color
alone.

Map marker popups must show only public-safe data.

Do not expose private coordinates or private images in map
responses.

Provide a non-map list alternative for accessibility and
low-bandwidth use.

12. Security, privacy, and responsible operation

Security is a release requirement, not a later enhancement.

12.1 Authentication and access

Argon2id password hashing.

Short-lived access tokens and rotating/revocable refresh sessions.

Secure, HttpOnly, SameSite refresh cookie where applicable.

CSRF protection when cookie-based authentication is used.

Strict CORS allowlist.

Role, organization, department, and service-area authorization.

Login and sensitive-action rate limiting.

Account suspension and session revocation.

12.2 Input and upload security

Server-side Pydantic validation.

Parameterized ORM/database queries.

File size and image format allowlists.

Verify actual file content; reject SVG and executable formats for
MVP.

Randomized storage identifiers; never trust user filenames.

Restrict Cloudinary transformations and upload parameters.

Avoid public image delivery by default; use controlled access or
approved derivatives.

Protect against stored XSS by escaping rendered user content.

Add security headers and HTTPS in production.

12.3 Privacy and data governance

Publish a privacy notice before accepting real pilot users.

Collect only data necessary to process reports.

Explain geolocation use and request browser permission only when
needed.

Separate private reporter data from public complaint data.

Define retention and deletion procedures with the pilot
organization.

Provide a contact route for privacy questions and correction
requests.

Restrict access to evidence images.

Do not send direct identifiers to Gemini.

Review applicable Indian data-protection obligations and obtain
appropriate institutional/legal guidance before a public pilot. This
specification is not legal advice.

12.4 Auditability

Record staff assignment, status, category, priority, department,
visibility, rejection, and resolution changes.

Audit records must identify actor, action, entity, timestamp, and
limited metadata.

Restrict audit-log access to administrators.

Do not log passwords, access tokens, refresh tokens, or full
sensitive payloads.

12.5 Abuse prevention

Rate-limit complaint creation and authentication.

Provide a report-review/moderation process for spam, abusive
content, and unrelated submissions.

Do not automatically publish potentially sensitive image content.

Allow staff to hide a public marker without deleting the underlying
complaint.

Preserve an audit trail for moderation decisions.

13. Configuration and environment variables

Create .env.example files containing placeholders only. Never commit
.env.

Backend configuration (names may be refined during implementation):

APP_ENV=development
APP_NAME=CivicFix AI
API_V1_PREFIX=/api/v1
SECRET_KEY=replace-with-long-random-secret
JWT_ISSUER=civicfix-ai
JWT_AUDIENCE=civicfix-ai-client
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/civicfix_ai
CORS_ORIGINS=http://localhost:5173

GEMINI_API_KEY=
GEMINI_MODEL=
GEMINI_TIMEOUT_SECONDS=30

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

PILOT_ORGANIZATION_NAME=
PILOT_AREA_NAME=
PUBLIC_MAP_DEFAULT_VISIBILITY=PRIVATE
MAX_UPLOAD_SIZE_MB=5
MAX_IMAGES_PER_COMPLAINT=4

Frontend .env.example:

VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=CivicFix AI
VITE_MAP_TILE_URL=

Rules: - Frontend variables prefixed with VITE_ are public. Never
place secrets in them. - Validate required environment variables at
backend startup. - Use separate credentials for development, staging,
and production. - Generate secrets with a secure random generator. - Do
not put real pilot personal data in development fixtures.

14. Testing strategy and acceptance criteria

Every phase must be tested before the next phase begins. A feature is
not complete merely because its page renders.

14.1 Backend tests

Unit tests for validation, state transitions, priority override
rules, duplicate scoring, and permissions.

API tests for registration, login, complaint creation, list/detail
access, assignment, status changes, notifications, and public
redaction.

Database integration tests using a dedicated test database.

Migration tests from an empty database to head.

AI tests using mocked Gemini responses; tests must not require a
live API key.

Cloudinary tests using mocked upload responses.

Security tests for IDOR, privilege escalation, invalid JWT, expired
token, refresh-token reuse, and unauthorized staff scope.

14.2 Frontend tests

Component tests for forms, validation, complaint cards, filters, map
states, and notifications.

Route/access tests for citizen, staff, and admin roles.

API error/loading/empty state tests.

Tests ensuring private data is not rendered in public views.

Build and TypeScript checks.

14.3 End-to-end pilot workflow

Citizen registers and logs in.

Citizen submits a complaint with a location and optional image.

Complaint is persisted even if AI is unavailable.

AI analysis completes or is marked failed/pending.

Potential duplicates are suggested where matching reports exist.

Authorized staff reviews and assigns the complaint.

Staff updates status and adds a public progress note.

Citizen receives an in-app notification.

Staff records resolution and uploads evidence.

Citizen sees the final status and can provide feedback.

Public map shows only approved, redacted complaint information.

Audit log records all authority actions.

14.4 Release gates

A phase passes only when: - The documented acceptance criteria pass. -
Automated tests pass. - No known critical/high-severity security defect
remains unresolved. - Database migrations apply cleanly. - The relevant
workflow is manually demonstrated. - Evidence is recorded in the project
README or phase checklist.

Do not claim a test passed unless its command was executed and its
result inspected.

15. Deployment and environments

15.1 Environments

Local development.

Staging/pilot verification.

Production/pilot.

Use separate databases and API credentials. Never use real pilot data in
local development unless explicitly authorized and protected.

15.2 Deployment target

Frontend: Vercel.

Backend: Render.

Database: managed PostgreSQL with backups.

Images: Cloudinary.

Maps: OpenStreetMap-compatible tile provider, subject to its usage
policy.

15.3 Deployment requirements

HTTPS everywhere.

Exact production CORS origins.

Secrets stored in hosting environment settings.

Database migrations executed as a controlled release step.

Health endpoint that does not disclose secrets.

Liveness/readiness checks.

Error monitoring and structured logs.

Database backup and restore procedure.

Defined rollback procedure.

Confirm provider terms, quotas, and usage policies before pilot
traffic.

Do not assume free hosting tiers are suitable for a reliable
real-world pilot; verify current limits and availability before
launch.

15.4 Operational readiness

Before inviting real citizens: - Obtain pilot organization
authorization. - Name the accountable person who monitors incoming
reports. - Confirm staff account ownership and offboarding. - Agree
categories, departments, service boundaries, escalation contacts, and
handling procedures. - Publish privacy notice and terms. - Test backup
restoration. - Test incident response and account revocation. - Run a
small closed pilot before public promotion. - Clearly state that
CivicFix AI is not an emergency-response service. Emergency situations
must use official emergency channels.

16. Development phases and Codex workflow

Build in small, verifiable milestones. Codex must read this file before
making changes.

Phase 0 --- Specification baseline

Deliverables: - This spec.md. - Architecture and database/API
documents when they are split out. - Confirmed pilot assumptions and
open questions.

Exit criteria: - Requirements are reviewed. - No unresolved decision
blocks project initialization.

Phase 1 --- Repository and development environment

Deliverables: - Git repository and .gitignore. - React/Vite/TypeScript
frontend scaffold. - FastAPI backend scaffold. - PostgreSQL local
setup. - Environment examples. - Health endpoint. - Basic CI checks if
practical.

Acceptance: - Frontend starts locally. - Backend starts locally. -
Backend health endpoint returns success. - Database connection is
verified. - No secrets are committed.

Phase 2 --- Database foundation and authentication

Deliverables: - SQLAlchemy models and Alembic migrations. - Citizen
registration/login. - JWT access and refresh flow. - Role and permission
dependencies. - Admin provisioning of staff.

Acceptance: - Migrations run from an empty database. - Passwords are
hashed. - Login and refresh tests pass. - Citizen cannot access
staff/admin APIs. - Staff cannot access another organization's data.

Phase 3 --- Complaint lifecycle

Deliverables: - Complaint creation and listing. - Complaint detail and
history. - Status transition service. - Assignment records. -
Public-safe complaint serializers.

Acceptance: - Citizen can submit and view own complaint. - Invalid
transitions are rejected. - Staff scope is enforced. - Public endpoints
do not leak private fields.

Phase 4 --- Image and map integration

Deliverables: - Secure Cloudinary upload flow. - Leaflet complaint form
location picker. - Public complaint map. - Privacy-aware coordinate
handling.

Acceptance: - Allowed images upload and are verified. -
Invalid/oversized files are rejected. - Public map only returns approved
markers. - Exact private location is not exposed.

Phase 5 --- AI and duplicate suggestions

Deliverables: - Gemini service adapter. - Structured Pydantic output
validation. - AI analysis persistence and failure handling. - Candidate
duplicate retrieval/scoring. - Staff duplicate review.

Acceptance: - Mocked AI tests pass without network access. - Invalid AI
output is safely rejected. - Complaint submission succeeds during AI
outage. - Duplicates are suggestions only; no automatic merge. - Staff
can confirm or dismiss a suggestion.

Phase 6 --- Authority and admin interfaces

Deliverables: - Staff queue and detail pages. - Assignment and status
workflows. - Admin user/department/category management. - Audit views.

Acceptance: - Staff can process an assigned complaint end-to-end. -
Admin can provision staff and configure departments. - Consequential
actions create audit records.

Phase 7 --- Citizen experience, notifications, analytics

Deliverables: - Citizen dashboard and complaint history. - In-app
notifications. - Feedback. - Role-specific charts.

Acceptance: - Citizen receives correct notifications. - Users cannot
read another user's notifications. - Analytics match database test
fixtures and respect scope.

Phase 8 --- Hardening and end-to-end testing

Deliverables: - Automated test suite. - Security review checklist. -
Error/empty/loading states. - Performance and accessibility checks. -
Pilot operations documentation.

Acceptance: - Full end-to-end workflow passes. - No unresolved
critical/high security issue. - Backup and restore procedure is tested.

Phase 9 --- Staging and pilot deployment

Deliverables: - Vercel frontend. - Render backend. - Managed
PostgreSQL. - Cloudinary production configuration. - Production
environment configuration. - Pilot onboarding checklist.

Acceptance: - Deployed health checks pass. - HTTPS and CORS work. -
Production migrations succeed. - Test accounts and a controlled test
complaint work. - Pilot authorization and privacy prerequisites are met
before real public use.

Codex instructions for every milestone

At the start of each milestone, instruct Codex to: 1. Read spec.md and
the current repository structure. 2. State which requirements and files
it intends to implement. 3. Identify assumptions or conflicts before
coding. 4. Implement only the current milestone; do not silently expand
scope. 5. Add or update tests with the implementation. 6. Run the
relevant lint, type-check, test, migration, and build commands. 7.
Report exact commands, pass/fail results, changed files, and known
limitations. 8. Never claim a command passed unless it was actually run.
9. Never overwrite existing user work without explaining the change. 10.
Update this specification only through an explicit, reviewed change.

17. Definition of Done

CivicFix AI MVP is complete only when:

Citizen, staff, and admin authentication/authorization work.

Citizens can submit and track civic complaints.

Images are securely stored and access-controlled.

AI classification, summary, priority, and department suggestions
work with validated output and graceful fallback.

Potential duplicates are detected and reviewed by humans.

Public map displays only approved and redacted data.

Staff can assign, update, and resolve complaints.

In-app notifications work.

Admin can manage pilot configuration and view analytics.

Audit history is retained for important actions.

Automated tests and full workflow tests pass.

The application is deployed to staging/production with HTTPS,
backups, and monitoring.

Pilot organization authorization, privacy notice, operational
ownership, and emergency disclaimer are in place before public pilot
launch.

README includes setup, architecture, environment variables, testing,
deployment, demo credentials policy, and screenshots.

18. Risks and mitigations

Risk                                Mitigation

Gemini unavailable or rate-limited  Persist complaint first; retry
safely; manual triage fallback

Incorrect AI priority               Human confirmation and override
with reason

False duplicate match               Suggest only; preserve both
reports; human review

Public exposure of personal data    Separate public schemas,
conservative visibility, privacy
tests

Unauthorized staff access           Organization/department scope
checks and IDOR tests

Malicious image uploads             Strict allowlist, content
verification, size limits,
controlled storage

No authority partner for pilot      Run a clearly labelled closed
demonstration; do not imply
endorsement

Hosting free-tier limitations       Verify quotas and use a suitable
paid/managed tier if needed

19. Open decisions to resolve before a live pilot

These do not block local development, but must be decided before
accepting real public reports:

Which organization has authorized the pilot?

What exact geographic boundary is covered?

Which departments and staff are responsible for each category?

Who monitors new complaints and during what hours?

What are the escalation and emergency disclaimers?

What location precision is safe for the public map?

What is the retention period for complaints, images, and audit logs?

Who handles privacy requests and account removal?

Which service-level targets, if any, has the participating authority
approved?

What hosting, backup, and operational budget is available?

Until these are resolved, use test data or a restricted pilot
environment and display an accurate pilot disclaimer.

20. Change control

This file is the baseline single source of truth.

Do not implement features that conflict with this specification
without first proposing a change.

Record each approved change with date, reason, affected sections,
and migration impact.

Keep API schemas, database migrations, tests, and UI behavior
consistent with the approved specification.

If implementation reality requires a deviation, document it and
obtain approval before treating it as the new baseline.

End of specification.