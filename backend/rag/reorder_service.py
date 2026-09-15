import os


class ReorderService:

    def __init__(self):

        import torch

        self.model_path = os.getenv("RERANKER_MODEL_PATH",r"D:\Hugging_Face\models\bge-reranker-v2-m3",)#r防/转义字符

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = None

    def get_model(self):
        from sentence_transformers import CrossEncoder

        if self.model is None:
            self.model = CrossEncoder(
                self.model_path,
                max_length=512,
                device=self.device,
                local_files_only= True,#只读本地文件
            )
            self.model.eval() #开启推理模式

        return self.model

    async def reorder_documents(self,query : str,documents : list[str], metadata : list[dict] | None = None, retrieval_scores : list[float] | None = None):

        if not documents:
            return []

        pairs = [(query,document) for document in documents] #list[(query,doc)]

        model = self.get_model()

        scores = model.predict(pairs,batch_size= 1 )

        result = []

        for index,(document,score) in enumerate(zip(documents,scores)):

            item = {
                "document" : document,
                "rerank_score":float(score),
                "similarity" : float(score)
            }

            if metadata:
                item["metadata"] = metadata[index]

            if retrieval_scores:
                item["retrieval_score"] = retrieval_scores[index]

            result.append(item)

        return sorted(
            result,
            key = lambda item: item["similarity"],
            reverse=True,
        )