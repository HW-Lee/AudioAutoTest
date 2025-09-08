class ActivityStateMachine(object):

    def __init__(self, device, serialno):
        self.device = device
        self.serialno = serialno
        self.cache = None

    def get_state(self):
        raise NotImplementedError(
            "the ActivityStateMachine.get_state() is not defined in the base class."
        )
