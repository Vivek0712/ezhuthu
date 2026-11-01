"""The infra Lambda proxy envelope (infra/README.md) is adapted to the runtime's action payload."""

from ezhuthu.agentcore_app import handle_proxy


class _Svc:
    def lesson(self, **kw):
        return {"session_id": kw["session_id"], "items": []}

    def answer(self, session_id, item_id, answer):
        return {"correct": answer == "ma"}


def test_lesson_reuses_proxy_minted_session_id():
    out = handle_proxy({"version": 1, "route": "/api/lesson", "body": {"level": "L1"}, "session_id": "s-1"}, _Svc())
    assert out == {"status": 200, "body": {"session_id": "s-1", "items": []}}


def test_errors_become_contract_status_and_body():
    out = handle_proxy({"version": 1, "route": "/api/answer", "body": {"session_id": "s-1"}}, _Svc())
    assert out["status"] == 422 and out["body"]["error"]["code"] == "bad_request"


def test_unknown_route_is_404_and_action_payload_passes_through():
    assert handle_proxy({"route": "/api/nope", "body": {}}, _Svc())["status"] == 404
    assert handle_proxy({"action": "answer", "session_id": "s", "item_id": "i", "answer": "ma"}, _Svc()) == {"correct": True}
