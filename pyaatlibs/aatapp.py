import os


class AATApp(object):
    INTENT_PREFIX = "am broadcast -a"
    HTC_INTENT_PREFIX = "audio.htc.com.intent."

    PACKAGE = "com.htc.audiofunctionsdemo"
    MAINACTIVITY = ".activities.MainActivity"

    @staticmethod
    def relaunch_app(device):
        device.shell("am force-stop {}".format(AATApp.PACKAGE))
        AATApp.launch_app(device)

    @staticmethod
    def launch_app(device):
        component = AATApp.PACKAGE + "/" + AATApp.MAINACTIVITY
        device.startActivity(component=component)

    @staticmethod
    def playback_nonoffload(device, filename="440Hz.wav"):
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "playback.nonoffload",
            "--es",
            "file",
            filename,
        ])
        device.shell(cmd)

    @staticmethod
    def playback_offload(device, filename="440Hz.mp3"):
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "playback.offload",
            "--es",
            "file",
            filename,
        ])
        device.shell(cmd)

    @staticmethod
    def playback_stop(device):
        cmd = " ".join([AATApp.INTENT_PREFIX, AATApp.HTC_INTENT_PREFIX + "playback.stop"])
        device.shell(cmd)

    @staticmethod
    def record_start(device):
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "record.start",
            "--ei",
            "spt_xmax",
            "1000",
        ])
        device.shell(cmd)

    @staticmethod
    def record_stop(device):
        cmd = " ".join([AATApp.INTENT_PREFIX, AATApp.HTC_INTENT_PREFIX + "record.stop"])
        device.shell(cmd)

    @staticmethod
    def record_dump(device, path):
        cmd = " ".join(
            [AATApp.INTENT_PREFIX, AATApp.HTC_INTENT_PREFIX + "record.dump", "--es", "path", path]
        )
        device.shell(cmd)

    @staticmethod
    def voip_start(device):
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "voip.start",
            "--ei",
            "spt_xmax",
            "1000",
        ])
        device.shell(cmd)

    @staticmethod
    def voip_stop(device):
        cmd = " ".join([AATApp.INTENT_PREFIX, AATApp.HTC_INTENT_PREFIX + "voip.stop"])
        device.shell(cmd)

    @staticmethod
    def voip_use_speaker(device, use=True):
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "voip.switch.speaker",
            "--ez",
            "use",
            str(1 if use else 0),
        ])
        device.shell(cmd)

    @staticmethod
    def voip_use_receiver(device):
        AATApp.voip_use_speaker(device, use=False)

    @staticmethod
    def voip_mute_output(device):
        cmd = " ".join([AATApp.INTENT_PREFIX, AATApp.HTC_INTENT_PREFIX + "voip.mute.output"])
        device.shell(cmd)

    @staticmethod
    def print_log(device, severity="i", tag="AATAppAPIs", log=None):
        if not log:
            return
        cmd = " ".join([
            AATApp.INTENT_PREFIX,
            AATApp.HTC_INTENT_PREFIX + "log.print",
            "--es",
            "sv",
            str(severity),
            "--es",
            "tag",
            str(tag),
            "--es",
            "log",
            '"{}"'.format(log),
        ])
        device.shell(cmd)


import threading
import time
from pyaatlibs.audiofunction import ToneDetectorThread, ToneDetector
from pyaatlibs.logger import Logger
from pyaatlibs.adbutils import Adb


class AATAppToneDetectorThread(ToneDetectorThread):

    def __init__(self, serialno, target_freq, callback):
        super(AATAppToneDetectorThread, self).__init__(target_freq=target_freq, callback=callback)
        self.serialno = serialno

    def push_to_dump(self, msg):
        self.extra["dump-lock"].acquire()
        self.extra["dump"].append(msg)
        self.extra["dump-lock"].release()

    def clear_dump(self):
        self.extra["dump-lock"].acquire()
        del self.extra["dump"][:]
        self.extra["dump-lock"].release()

    def get_tag(self):
        return "AATAppToneDetectorThread"

    def set_target_frequency(self, target_freq):
        if type(target_freq) is list:
            target_freq = target_freq[0]

        self.target_freq = target_freq

    def dump(self):
        self.extra["dump-lock"].acquire()
        Logger.log(self.get_tag(), "dump called")
        Logger.log(self.get_tag(), "----------------------------------------------")
        for msg in self.extra["dump"]:
            Logger.log("{}::dump".format(self.get_tag()), '"{}"'.format(msg))
        del self.extra["dump"][:]
        Logger.log(self.get_tag(), "----------------------------------------------")
        self.extra["dump-lock"].release()

    def join(self, timeout=None):
        super(AATAppToneDetectorThread, self).join(timeout=timeout)

    def run(self):
        shared_vars = {"start_time": None, "last_event": None, "last_freq": -1}

        self.extra = {}
        self.extra["adb-read-prop-max-elapsed"] = -1
        self.extra["freq-cb-max-elapsed"] = -1
        self.extra["dump"] = []
        self.extra["dump-lock"] = threading.Lock()

        def freq_cb(msg):
            line = msg.splitlines()[0]
            strs = line.split()
            freq, amp_db = list(map(float, strs[-1].split(",")))
            the_date, the_time = strs[:2]

            time_str = the_date + " " + the_time

            if shared_vars["last_freq"] != freq:
                self.push_to_dump(
                    "the detected freq has been changed from {} to {} Hz".format(
                        shared_vars["last_freq"], freq
                    )
                )
                shared_vars["last_freq"] = freq

            thresh = 10 if self.target_freq else 1
            if super(AATAppToneDetectorThread, self).target_detected(freq):
                self.event_counter += 1
                if self.event_counter == 1:
                    shared_vars["start_time"] = time_str
                if self.event_counter == thresh:
                    if (
                        not shared_vars["last_event"]
                        or shared_vars["last_event"] != ToneDetector.Event.TONE_DETECTED
                    ):
                        Logger.log(
                            self.get_tag(),
                            "send_cb({}, TONE_DETECTED)".format(shared_vars["start_time"]),
                        )
                        self.cb((shared_vars["start_time"], ToneDetector.Event.TONE_DETECTED))
                        shared_vars["last_event"] = ToneDetector.Event.TONE_DETECTED

            else:
                if self.event_counter > thresh:
                    shared_vars["start_time"] = None
                    self.push_to_dump(
                        "the tone is not detected and the event_counter is over the threshold"
                    )
                    self.push_to_dump('last_event: "{}"'.format(shared_vars["last_event"]))
                if (
                    not shared_vars["last_event"]
                    or shared_vars["last_event"] != ToneDetector.Event.TONE_MISSING
                ):
                    Logger.log(self.get_tag(), "send_cb({}, TONE_MISSING)".format(time_str))
                    self.cb((time_str, ToneDetector.Event.TONE_MISSING))
                    shared_vars["last_event"] = ToneDetector.Event.TONE_MISSING
                self.event_counter = 0

            if self.event_counter <= thresh:
                self.push_to_dump("event_counter: {}".format(self.event_counter))

        # Adb.execute(cmd= \
        #     ["shell", "am", "broadcast", "-a", "audio.htc.com.intent.print.properties.enable", "--ez", "v", "1"], \
        #     serialno=self.serialno)

        from pyaatlibs.timeutils import TicToc, TimeUtils

        freq_cb_tictoc = TicToc()
        adb_tictoc = TicToc()

        tcount = 0
        freq_cb_tictoc.tic()
        while not self.stoprequest.isSet():
            adb_tictoc.tic()
            msg, _ = Adb.execute(
                cmd=["shell", "cat", "sdcard/AudioFunctionsDemo-record-prop.txt"],
                serialno=self.serialno,
                tolog=False,
            )
            elapsed = adb_tictoc.toc()
            if tcount == 0:
                Adb.execute(
                    cmd=["shell", "rm", "-f", "sdcard/AudioFunctionsDemo-record-prop.txt"],
                    serialno=self.serialno,
                    tolog=False,
                )

            if not "," in msg:
                msg = "0,-30"

            if elapsed > self.extra["adb-read-prop-max-elapsed"]:
                self.extra["adb-read-prop-max-elapsed"] = elapsed

            if "," in msg:
                msg = msg.replace("\n", "")
                import datetime

                msg = "{} {}".format(TimeUtils.now_str(), msg)

                try:
                    self.push_to_dump("{} (adb-shell elapsed: {} ms)".format(msg, elapsed))
                    freq_cb(msg)
                except Exception as e:
                    Logger.log(self.get_tag(), "crashed in freq_cb('{}')".format(msg))
                    print(e)

                elapsed = freq_cb_tictoc.toc()
                if elapsed > self.extra["freq-cb-max-elapsed"]:
                    self.extra["freq-cb-max-elapsed"] = elapsed

            time.sleep(0.01)
            tcount += 1
            tcount %= 10

        # Adb.execute(cmd= \
        #     ["shell", "am", "broadcast", "-a", "audio.htc.com.intent.print.properties.enable", "--ez", "v", "0"], \
        #     serialno=self.serialno)
