
import logging
from datetime import datetime, timezone

from db.redis_client import get_redis
from utils.cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)
MAX_BUFFER_TURNS = 8
MAX_RECENT_TURNS = 4
KEEP_RECENT_TURNS = 4
MAX_FIELD_ITEMS = 10
MAX_ITEM_CHARS = 240
MAX_SUMMARY_CHARS = 3000
MAX_CONTEXT_CHARS = 6000
class WorkingMemoryService:
    ttl = 60*60*24

    @staticmethod
    def _key(user_id : int , session_id : str):
        return f"working-memory:{user_id}:{session_id}"

    async def get(self,user_id : int ,session_id : str):
        return await cache_get_json(self._key(user_id, session_id))

    async def save(self,user_id:int,session_id:str,state:dict,):
       await cache_set_json(self._key(user_id, session_id),state,self.ttl)

    async def record_turn(self,user_id:int,session_id:str,user_message:str,assisant_message:str):
        state = await self.get(user_id, session_id) or {}

        recent_turns = state.setdefault("recent_turns",[])
        recent_turns.append(
            {
                "user":self._clip(user_message,1000),
                "assistant":self._clip(assisant_message,1000),
            }
        )

        state["recent_turns"] = recent_turns[-MAX_BUFFER_TURNS:]
        state["turn_count"] = int(state.get("turn_count", 0)) + 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.save(user_id, session_id, state)

    async def patch(self,user_id:int,session_id:str,patch:dict):
        state = await self.get(user_id, session_id) or {}
        for field in ("goal","constraints","decisions","open_questions"):
            value = patch.get(field)

            if value is None:
                continue

            if field == "goal":
                state[field] = self._clip(value,500)
                continue

            if isinstance(value,str):
                value = [value]

            old_values = state.setdefault(field,[])

            for item in value:
                item = self._clip(item,MAX_ITEM_CHARS)
                if item and item not in old_values:
                    old_values.append(item)

            state[field] = old_values[-MAX_FIELD_ITEMS:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self.save(user_id, session_id, state)

    async def clear(self,user_id:int,session_id:str,):
        try:
            await get_redis().delete(
                self._key(user_id, session_id)
            )
        except Exception as exc:
            logger.warning("清理工作记忆失败：%s", exc)

    @staticmethod
    def _clip(value,limit):
        text = str(value or "").strip()
        if len(text) <= limit:
            return text

        return text[:limit - 1] + "..."


    async def compact(self,user_id,session_id,summarize):
        state = await self.get(user_id, session_id) or {}
        recent_turns = list(state.get("recent_turns") or [])

        if len(recent_turns) <= MAX_BUFFER_TURNS:
            return False

        old_turns = recent_turns[:-KEEP_RECENT_TURNS]
        previous_summary = state.get("summary", "")

        try:
            new_summary = await summarize(previous_summary, old_turns)
        except Exception as exc:
            logger.warning("工作记忆压缩失败：%s", exc)
            return False
        new_summary = self._clip(new_summary, MAX_SUMMARY_CHARS)

        if not new_summary:
            return False

        state["summary"] = new_summary
        state["recent_turns"] = recent_turns[-KEEP_RECENT_TURNS:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.save(user_id, session_id, state)
        return True


    @staticmethod
    def format_context(state,max_chars=MAX_CONTEXT_CHARS):

        if not state:
            return ""

        parts = []
        if state.get("summary"):
            parts.append(
                "此前工作摘要：\n"
                + WorkingMemoryService._clip(
                state["summary"],
                MAX_SUMMARY_CHARS,
            )
            )

        if state.get("goal"):
            parts.append("当前目标："+WorkingMemoryService._clip(state["goal"],500))

        for field,title in (
            ("constraints", "约束"),
            ("decisions", "已确认决策"),
            ("open_questions", "待解决问题"),
        ):
            values = state.get(field,[])[-MAX_FIELD_ITEMS:]
            if values:
                lines = [
                    f"- {WorkingMemoryService._clip(item, MAX_ITEM_CHARS)}"
                    for item in values
                ]
                parts.append(f"{title}：\n" + "\n".join(lines))

        recent_turns = (state.get("recent_turns") or [])[-KEEP_RECENT_TURNS:]
        if recent_turns:
            parts.append(
                "最近工作上下文：\n"
                + "\n\n".join(
                    "用户："
                    + WorkingMemoryService._clip(item.get("user"), 600)
                    + "\n助手："
                    + WorkingMemoryService._clip(item.get("assistant"), 800)
                    for item in recent_turns
                )
            )
        result = "\n\n".join(parts)
        if len(result) > max_chars:
            return result[: max_chars - 20] + "\n[工作记忆已截断]"

        return result



