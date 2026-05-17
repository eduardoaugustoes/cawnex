# API Contract: Project State Field

## Overview

The `state` field in the `GET /projects/{id}` API response contains computed project state information derived from the project's execution reality (Monarch docs, waves, MVIs, council decisions).

## Field Structure

The `state` object returned by the backend has the following structure:

```json
{
  "state": {
    "crow_count": 12,
    "mvi_queue_count": 2,
    "wave_status": {
      "status": "running",
      "elapsed_seconds": 9000,
      "started_at": "2026-05-13T10:00:00Z"
    },
    "council_decision": {
      "approved_count": 4,
      "security_flag_count": 1,
      "other_count": 0
    }
  }
}
```

## Field Descriptions

### crow_count
- **Type**: Integer
- **Description**: The number of crows (autonomous agents) that have completed their work.
- **Example**: `12` means 12 crows have completed their tasks.

### mvi_queue_count
- **Type**: Integer
- **Description**: The number of MVIs (Minimum Viable Implementations) awaiting founder/council review.
- **Example**: `2` means 2 items are in the approval queue.

### wave_status
An object describing the current wave execution state:

- **status** (String): One of `"running"`, `"idle"`, `"paused"`
- **elapsed_seconds** (Integer, optional): Elapsed time in seconds since the wave started. Only present when `status == "running"`
- **started_at** (ISO8601 String, optional): Timestamp when the wave started. Only present when `status == "running"`

### council_decision
Optional object describing council approval status:

- **approved_count** (Integer): Number of council members who approved
- **security_flag_count** (Integer): Number of security flags raised
- **other_count** (Integer): Number of other decision types (e.g., abstain)

## Example Responses by Project State

### Project in Draft (Monarch Generating Docs)

```json
{
  "project_id": "p_abc123",
  "name": "Cawnex",
  "current_state": "draft",
  "state": {
    "crow_count": 0,
    "mvi_queue_count": 0,
    "wave_status": {
      "status": "idle"
    },
    "council_decision": null
  }
}
```

### Project Setup Complete, No Waves Yet

```json
{
  "project_id": "p_abc123",
  "name": "Cawnex",
  "current_state": "active",
  "state": {
    "crow_count": 0,
    "mvi_queue_count": 0,
    "wave_status": {
      "status": "idle"
    },
    "council_decision": null
  }
}
```

### Project with Running Wave

```json
{
  "project_id": "p_abc123",
  "name": "Cawnex",
  "current_state": "running",
  "state": {
    "crow_count": 12,
    "mvi_queue_count": 2,
    "wave_status": {
      "status": "running",
      "elapsed_seconds": 9000,
      "started_at": "2026-05-13T10:00:00Z"
    },
    "council_decision": null
  }
}
```

### Project with Running Wave and Pending Council Review

```json
{
  "project_id": "p_abc123",
  "name": "Cawnex",
  "current_state": "running",
  "state": {
    "crow_count": 15,
    "mvi_queue_count": 1,
    "wave_status": {
      "status": "running",
      "elapsed_seconds": 14400,
      "started_at": "2026-05-13T09:00:00Z"
    },
    "council_decision": {
      "approved_count": 4,
      "security_flag_count": 1,
      "other_count": 0
    }
  }
}
```

### Project Completed

```json
{
  "project_id": "p_abc123",
  "name": "Cawnex",
  "current_state": "completed",
  "state": {
    "crow_count": 20,
    "mvi_queue_count": 0,
    "wave_status": {
      "status": "idle"
    },
    "council_decision": {
      "approved_count": 5,
      "security_flag_count": 0,
      "other_count": 0
    }
  }
}
```

## iOS Decoding

The `ProjectState` Swift struct in `apps/ios/Cawnex/Cawnex/Domain/ProjectState.swift` automatically decodes this JSON structure via `Decodable`.

Computed properties on `ProjectState` provide formatted strings for UI display:

- `crowCompletionLabel`: e.g., "12 of 15 Crows completed"
- `mviQueueLabel`: e.g., "2 awaiting founder review"
- `waveStatusLabel`: e.g., "Running • 2h 30m elapsed" or "Idle"
- `councilSummary`: e.g., "Council: 4 approve, 1 security flag"

## Backend Implementation

The state field is computed by `compute_current_state()` in `apps/api/src/db/project_state.py` and injected into all project responses:

- `GET /projects` — lists all projects with state
- `GET /projects/{id}` — returns single project with state
- `POST /projects` — creation response includes initial state (always draft)

For more details on the computation logic, see `apps/api/src/db/project_state.py`.
