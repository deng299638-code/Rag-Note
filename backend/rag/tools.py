from langchain_core.tools import tool
from rag.NoteRagService import NoteRagService
from schemas.note_schemas import NoteCreate
from services.note_service import NoteService


def build_note_tools(note_service : NoteService,note_rag: NoteRagService,user_id : int):
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

    return [get_note_stats,search_notes,create_note,get_related_notes]

