"""Focused offline checks for the Level 1 vertical slice foundations."""

import asyncio

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.agents import auditor, sensor
from backend.app.ledger import ResourceLedger
from backend.app.models import Action, Comms, Incident, ModeRequest, Plan
from backend.app.orchestrator import AgentContext, run_sample
from backend.app.store import AegisStore


def test_sample_runs_through_five_agents_and_survives_restart(tmp_path) -> None:
    database = tmp_path / "aegis.sqlite3"
    data_store = AegisStore(database)
    resource_ledger = ResourceLedger()

    plan = asyncio.run(
        run_sample(data_store=data_store, resource_ledger=resource_ledger)
    )

    assert plan.status == "awaiting_approval"
    assert {step.agent for step in data_store.trace} >= {
        "sensor",
        "triage",
        "logistics",
        "comms",
        "auditor",
    }

    reopened = AegisStore(database)
    reopened_plan = reopened.get_plan(plan.id)
    assert reopened_plan is not None
    assert reopened_plan.status == "awaiting_approval"
    assert reopened.get_event(sensor.sample_event().id) is not None


def test_ledger_rejects_lower_priority_contention() -> None:
    resource_ledger = ResourceLedger()

    assert resource_ledger.reserve("fac-shared", "incident-high", 5)
    assert not resource_ledger.reserve("fac-shared", "incident-low", 3)
    assert resource_ledger.snapshot()[0]["incident_id"] == "incident-high"


def test_auditor_flags_unsupported_numbers_and_missing_evidence(tmp_path) -> None:
    data_store = AegisStore(tmp_path / "audit.sqlite3")
    evidence = data_store.create_evidence(
        "fixture",
        "Measured magnitude is 7.8.",
        {"magnitude": 7.8},
        evidence_id="e1",
    )
    incident = Incident(
        id="incident:test",
        event_ids=["event:test"],
        hazard="earthquake",
        det_score=3,
        priority=3,
        rationale="test",
        evidence_ids=[evidence.id],
    )
    plan = Plan(
        id="plan:test",
        incident_id=incident.id,
        actions=[
            Action(
                type="public_alert",
                target="zone",
                detail="test",
                evidence_ids=["missing-evidence"],
            )
        ],
        comms=[
            Comms(
                channel="sms",
                en="M9.1 event",
                hi="9.1 घटना",
                evidence_ids=[evidence.id],
            )
        ],
        status="auditing",
    )

    result = asyncio.run(
        auditor.run(plan, incident, AgentContext(data_store, ResourceLedger()))
    )

    assert result.verdict == "revise"
    assert any("Missing evidence" in flag for flag in result.flags)
    assert any("unsupported number" in flag for flag in result.flags)


def test_compound_replay_processes_both_offline_events() -> None:
    async def scenario() -> None:
        main.store.clear()
        main.ledger.reset()
        await main.set_mode(
            ModeRequest(mode="replay", scenario="compound_synthetic", speed=60)
        )
        assert main.replay_task is not None
        await asyncio.wait_for(main.replay_task, timeout=2)
        await main.state()
        assert len(main.store.list_events()) == 2
        assert len(main.store.list_incidents()) == 2
        assert all(plan.status == "awaiting_approval" for plan in main.store.list_plans())
        assert any("Contention" in step.message for step in main.store.trace)
        main.store.clear()
        main.ledger.reset()

    asyncio.run(scenario())


def test_api_inject_and_approve_writes_audit_log() -> None:
    main.store.clear()
    main.ledger.reset()
    with TestClient(main.app) as client:
        injected = client.post("/api/dev/inject-sample")
        assert injected.status_code == 200
        plan = injected.json()
        assert plan["status"] == "awaiting_approval"

        approved = client.post(
            f"/api/plans/{plan['id']}/approve",
            json={"note": "Reviewed in the offline demo."},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        audit = client.get("/api/audit-log")
        assert audit.status_code == 200
        assert audit.json()[-1]["decision"] == "approved"
        assert audit.json()[-1]["note"] == "Reviewed in the offline demo."

    main.store.clear()
    main.ledger.reset()
