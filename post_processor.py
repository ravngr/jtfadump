class PostProcessor:
    def __init__(self, cfg):
        self._cfg = cfg

    @staticmethod
    def get_supported_data_capture(self):
        raise NotImplementedError()

    def process(self, data):
        raise NotImplementedError()
