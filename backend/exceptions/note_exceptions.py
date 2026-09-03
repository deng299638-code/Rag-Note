

class NoteNotFoundError(Exception):
    def __init__(self,note_id:int):
        self.note_id = note_id
        super.__init__(f"笔记不存在：{note_id}")

