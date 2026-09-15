from typing import Any


def assess_rerank_confidence(ranked:list[dict[str,Any]],*,min_score:float,min_margin:float):
    if not ranked:
        return {
            "decision": "reject",
            "reason": "没有检索结果",
            "top_score": None,
            "margin": None,
            "candidate_count": 0,
        }

    def get_score(item:dict[str,Any]):
        return item.get("rerank_score",item.get("similarity",0.0))

    top_score = get_score(ranked[0])

    second_score = (get_score(ranked[1]) if len(ranked) > 1 else None)

    margin = (top_score - second_score if second_score is not None else None)

    if top_score < min_score:
        decision = "reject"
        reason = "最高重排分数过低"

    elif margin is not None and margin < min_margin:
        decision = "uncertain"
        reason = "第一名和第二名差距太小"

    else:
        decision = "accept"
        reason = "结果分数和排序差距均满足要求"

    return {
        "decision": decision,
        "reason": reason,
        "top_score": top_score,
        "margin": margin,
        "candidate_count": len(ranked),
    }