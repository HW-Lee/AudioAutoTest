import datetime
import time
import threading


class Timer(threading.Thread):

    def __init__(self, period_ms=1):
        super(Timer, self).__init__()
        self.timer = TicToc()
        self.running = False
        self._timer_lock = threading.Lock()
        self.time_ms = 0
        self._time_ms_lock = threading.Lock()
        self.stoprequest = threading.Event()
        self.period_ms = period_ms
        self.daemon = True

    def _update(self):
        with self._time_ms_lock:
            self.time_ms += self.timer.toc()

    def get_time(self):
        with self._time_ms_lock:
            time_ms = self.time_ms

        return time_ms

    def reset(self):
        with self._time_ms_lock:
            self.time_ms = 0

    def pause(self):
        with self._timer_lock:
            self.running = False
            self.timer = TicToc()

    def resume(self):
        with self._timer_lock:
            self.running = True

    def join(self):
        self.stoprequest.set()
        super(Timer, self).join(timeout=10)

    def run(self):
        self.resume()
        while not self.stoprequest.isSet():
            with self._timer_lock:
                running = self.running

            if not running:
                time.sleep(self.period_ms / 1000.0)
                continue

            self._update()
            time.sleep(self.period_ms / 1000.0)


def TicTocGenerator():
    tf = datetime.datetime.now()
    while True:
        ti = tf
        tf = datetime.datetime.now()
        yield (tf - ti).total_seconds()


class TicToc(object):

    def __init__(self):
        self.tictoc = TicTocGenerator()

    def toc(self):
        return next(self.tictoc) * 1000.0

    def tic(self):
        next(self.tictoc)


class TimeUtils(object):
    TIME_STR_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
    TIME_UNITS = ["d", "h", "m", "s"]

    @staticmethod
    def now_str():
        return TimeUtils.str_from_time(datetime.datetime.now())

    @staticmethod
    def str_from_time(t):
        return datetime.datetime.strftime(t, TimeUtils.TIME_STR_FORMAT)

    @staticmethod
    def time_from_str(s):
        return datetime.datetime.strptime(s, TimeUtils.TIME_STR_FORMAT)

    @staticmethod
    def pretty_str(ms):
        if ms <= 0:
            return "0s"
        t = datetime.datetime.fromtimestamp(ms / 1000.0) - datetime.datetime.fromtimestamp(0)
        t = [
            str(int(s)) if s.isdigit() else str(float(s))
            for s in str(t).replace(" days, ", ":").split(":")
            if float(s) > 0
        ]
        s = "{} ".join(t) + "{}"
        s = s.format(*TimeUtils.TIME_UNITS[-len(t) :])
        return s
