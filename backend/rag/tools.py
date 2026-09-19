from langchain_core.tools import tool
from rag.NoteRagService import NoteRagService
from schemas.note_schemas import NoteCreate
from services.long_term_memory import LongTermMemoryService
from services.note_service import NoteService


def build_note_tools(note_service : NoteService,note_rag: NoteRagService,user_id : int,memory_service : LongTermMemoryService | None = None,working_memory=None,session_id: str | None = None,):
    @tool(
        "get_note_stats",
        description="当用户询问笔记总数、分类数量或笔记统计时调用。"
    )
    async def get_note_stats():

        stats = await note_service.get_stats(user_id)

        if stats["total"] == 0:
            return "用户目前还没有笔记。"

        lines = [f"笔记总数：{stats['total']} 篇"]

        if stats["categories"]:

            lines.append("分类统计:")

        lines.extend(
            f"- {item['category']}：{item['count']} 篇"
            for item in stats["categories"]
        )

        if stats["uncategorized"]:
            lines.append(f"- 未分类：{stats['uncategorized']} 篇")

        return "\n".join(lines)

    @tool(
        "search_notes",
        description= "当用户明确要求搜索、查找、列出或寻找相关笔记时调用。"
        "参数 query 必须是从用户问题中提取的检索关键词。"
    )
    async def search_notes(query:str):

        results = await note_rag.search_notes(query,user_id)

        if not results:
            return "没有找到相关笔记。"

        return "\n\n".join(
        (f"{index}. {item['document']}" for index, item in enumerate(results, start=1))
    )

    @tool(
        "create_note",
        description= "仅当用户明确要求创建、保存或记录一篇笔记时调用。"
        "参数 title 是笔记标题，content 是笔记正文。"
    )
    async def create_note(title,content):
        try:
            note =  await note_service.create(user_id,payload=NoteCreate(title=title, content=content))

        except Exception:
            return "笔记创建失败，请检查标题和内容后重试。"

        return (
            "笔记已经创建\n"
            f"ID:{note.id}"
            f"标题:{note.title}"
        )


    @tool(
        "get_related_notes",
        description=(
                "当用户要求查找某篇笔记的相似笔记或关联资料时调用。"
                "参数 note_id 是笔记 ID，top_k 是返回数量。"
        )
    )
    async def get_related_notes(note_id : int, top_k : int = 3):
        try:

            source_note = await note_service.get_owned(note_id,user_id)

            result = await note_rag.search_notes(source_note.content,user_id,top_k + 1)

        except Exception:
            return "获取关联笔记失败，请检查笔记 ID 是否正确。"

        results = [
            item
            for item in result
            if str(item.get("metadata",{}).get("note_id")) != str(note_id)
        ][:top_k]

        if not  results:
            return "没有找到关联笔记。"

        lines = [f"共找到{len(results)}篇笔记:\n\n"]

        for index,item in enumerate(results,start=1):
            metadata = item.get("metadata",{})
            title = metadata.get("title","无标题")

            lines.append(
                f"{index}.{title}\n"
                f"相似度:{item['similarity']:.4f}\n"
                f"内容:{item['document']}"
            )
        return "\n\n".join(lines)

    tools = [get_note_stats,search_notes,create_note,get_related_notes]
    if memory_service is not None:
        @tool(
            "remember_user_memory",
            description=(
                    "只有用户明确说‘记住、保存、以后都这样’时才调用。"
                    "不要保存密码、Token、验证码等敏感信息。"
            ),
        )
        async def remember_user_memory(key: str, value: str, kind: str = "fact", ):
            try:
                await memory_service.remember(
                    user_id=user_id,
                    key=key,
                    content=value,
                    kind=kind,
                    source_session_id=session_id,
                )

                return f"已记住：{value}"
            except Exception as exc:
                return f"保存长期记忆失败：{exc}"

        @tool(
            "forget_user_memory",
            description="只有用户明确要求忘记某项长期记忆时才调用。",
        )
        async def forget_user_memory(key: str):
            deleted = await memory_service.forget(
                user_id=user_id,
                key=key,
            )
            return "已删除。" if deleted else "没有找到这条记忆。"

        tools.extend(
            [
                remember_user_memory,
                forget_user_memory,
            ]
        )

    if working_memory is not None:
        @tool(
            "update_working_memory",
            description=(
                     "当当前任务目标、约束、决策或待解决问题发生变化时调用。"
                     "这里只保存当前会话临时状态，不保存永久用户偏好。"
            ),
        )
        async def update_working_memory(goal: str = "",constraints: str = "",decisions: str = "",open_questions: str = "",):
            patch = {}
            if goal.strip():
                patch["goal"] = goal.strip()

            for field,value in (
                ("constraints", constraints),
                ("decisions", decisions),
                ("open_questions", open_questions),
            ):
                if value.strip():
                    patch[field] = [item.strip() for item in value.replace(":",";").split(";") if item.strip()]


            await working_memory.patch(
                user_id=user_id,
                session_id=session_id,
                patch=patch,
            )
            return "当前工作记忆已更新。"
        tools.append(update_working_memory)

    return tools

