class ChatSessionNotFoundError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(
            f"会话不存在或无权访问：{session_id}"
        )