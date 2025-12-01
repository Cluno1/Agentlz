import json
import agentlz.services.mcp_service as svc
from agentlz.schemas.check import ToolAssessment


def main():
    recorded = []

    def fake_get(ids):
        return [
            {"id": 23, "trust_score": 80},
            {"id": 34, "trust_score": 75},
        ]

    def fake_update_service(agent_id: int, payload):
        recorded.append({"id": agent_id, "new_trust": float(payload.get("trust_score", 0) or 0)})
        return {"id": agent_id, "trust_score": float(payload.get("trust_score", 0) or 0)}

    def fake_update_pg(agent_id: int, score: float):
        return None

    svc._get_mcp_agents_by_ids = fake_get
    svc.update_mcp_agent_service = fake_update_service
    svc._update_trust_pg = fake_update_pg

    assessments = [
        ToolAssessment(
            mcp_id="23",
            server="",
            status="success",
            raw_input="",
            raw_output="",
            error_msg="",
            micro_score=90,
            micro_judge=True,
            micro_reason="",
        ),
        ToolAssessment(
            mcp_id="exa_remote",
            server="exa_remote",
            status="error",
            raw_input="",
            raw_output="",
            error_msg="x",
            micro_score=85,
            micro_judge=False,
            micro_reason="",
        ),
    ]
    name_to_id = {"exa_remote": 34}

    svc.update_trust_by_tool_assessments(assessments, name_to_id)

    print(json.dumps({"updates": recorded}, ensure_ascii=False))


if __name__ == "__main__":
    main()

