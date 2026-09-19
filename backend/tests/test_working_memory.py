from unittest.mock import AsyncMock

import pytest

from services.WorkingMemoryService import WorkingMemoryService


@pytest.mark.asyncio
async def test_compact_keeps_summary_and_latest_four_turns():
    service = WorkingMemoryService()

    state = {
        "recent_turns": [
            {
                "user": f"问题 {index}",
                "assistant": f"回答 {index}",
            }
            for index in range(9)
        ]
    }

    service.get = AsyncMock(return_value=state)
    service.save = AsyncMock()

    async def summarize(previous_summary, old_turns):
        assert len(old_turns) == 5
        return "旧对话摘要"

    result = await service.compact(
        user_id=1,
        session_id="session-1",
        summarize=summarize,
    )

    assert result is True

    saved_state = service.save.await_args.args[2]

    assert saved_state["summary"] == "旧对话摘要"
    assert len(saved_state["recent_turns"]) == 4
    assert saved_state["recent_turns"][-1]["user"] == "问题 8"