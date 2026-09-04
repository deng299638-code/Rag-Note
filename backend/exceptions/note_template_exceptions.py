

class TemplateNotFoundError(Exception):
    def __init__(self,template_id: str):
        self.template_id = template_id
        super().__init__(f"模板不存在：{template_id}")


class InvalidTemplateOrderError(Exception):
    def __init__(
        self,
        message: str,
    ):
        super().__init__(message)