import threading
import numpy as np
import time
import os
import datetime

from pyaatlibs.audiothread import *
from pyaatlibs.adbutils import Adb
from pyaatlibs.logger import Logger
from pyaatlibs.timeutils import TimeUtils


# Initialization of used variables
class CommandHandler(object):

    def __init__(self):
        self.cmd = None

    def stop(self):
        if self.cmd:
            self.cmd.stop()


class AudioFunction(object):
    WORK_THREAD = AudioCommandThread()
    WORK_THREAD.daemon = True
    AUDIO_CONFIG = AudioConfig(fs=48000, ch=1)
    COMMAND = CommandHandler()

    HAS_BEEN_INIT = False

    @staticmethod
    def init():
        if AudioFunction.HAS_BEEN_INIT:
            return
        AudioFunction.WORK_THREAD.start()
        AudioFunction.HAS_BEEN_INIT = True

    @staticmethod
    def finalize():
        if not AudioFunction.HAS_BEEN_INIT:
            raise RuntimeError("The AudioFunction should be initialized before calling APIs")
        AudioFunction.WORK_THREAD.join()

        AudioFunction.HAS_BEEN_INIT = False

    @staticmethod
    def play_sound(out_freq):
        if not AudioFunction.HAS_BEEN_INIT:
            raise RuntimeError("The AudioFunction should be initialized before calling APIs")
        AudioFunction.COMMAND.stop()
        AudioFunction.COMMAND.cmd = TonePlayCommand(
            config=AudioFunction.AUDIO_CONFIG, out_freq=out_freq
        )
        AudioFunction.WORK_THREAD.push(AudioFunction.COMMAND.cmd)

    @staticmethod
    def stop_audio():
        AudioFunction.COMMAND.stop()

    @staticmethod
    def start_record(cb, cmd=None):
        if not AudioFunction.HAS_BEEN_INIT:
            raise RuntimeError("The AudioFunction should be initialized before calling APIs")
        AudioFunction.COMMAND.stop()
        AudioFunction.AUDIO_CONFIG.cb = cb
        AudioFunction.COMMAND.cmd = (
            cmd
            if cmd is not None
            else ToneDetectCommand(config=AudioFunction.AUDIO_CONFIG, framemillis=50, nfft=2048)
        )
        AudioFunction.WORK_THREAD.push(AudioFunction.COMMAND.cmd)


class ToneDetectorThread(threading.Thread):

    def __init__(self, target_freq, callback):
        super(ToneDetectorThread, self).__init__()
        self.daemon = True
        self.stoprequest = threading.Event()
        self.event_counter = 0
        self.target_freq = target_freq
        self.cb = callback
        self.extra = None

    def join(self, timeout=None):
        self.stoprequest.set()
        super(ToneDetectorThread, self).join(timeout)

    def run(self):
        raise RuntimeError("The base class does not have implemented run() function.")

    def target_detected(self, freq):
        if freq == 0:
            return False

        if self.target_freq == None:
            return True

        diff_semitone = np.abs(np.log(1.0 * freq / self.target_freq) / np.log(2) * 12)
        return diff_semitone < 2


class ToneDetectorForServerThread(ToneDetectorThread):

    def __init__(self, target_freq, callback):
        super(ToneDetectorForServerThread, self).__init__(
            target_freq=target_freq, callback=callback
        )

    def join(self, timeout=None):
        super(ToneDetectorForServerThread, self).join(timeout)

    def run(self):
        shared_vars = {"start_time": None, "last_event": None}

        def freq_cb(detected_tones):
            if len(detected_tones) == 0:
                return
            time_str = TimeUtils.now_str()
            freq, amp = detected_tones[0]

            thresh = 10 if self.target_freq else 1
            if super(ToneDetectorForServerThread, self).target_detected(freq):
                self.event_counter += 1
                if self.event_counter == 1:
                    shared_vars["start_time"] = time_str
                if self.event_counter == thresh:
                    if (
                        not shared_vars["last_event"]
                        or shared_vars["last_event"] != ToneDetector.Event.TONE_DETECTED
                    ):
                        self.cb((shared_vars["start_time"], ToneDetector.Event.TONE_DETECTED))
                        shared_vars["last_event"] = ToneDetector.Event.TONE_DETECTED

            else:
                if self.event_counter > thresh:
                    shared_vars["start_time"] = None
                    if (
                        not shared_vars["last_event"]
                        or shared_vars["last_event"] != ToneDetector.Event.TONE_MISSING
                    ):
                        self.cb((time_str, ToneDetector.Event.TONE_MISSING))
                        shared_vars["last_event"] = ToneDetector.Event.TONE_MISSING
                self.event_counter = 0

        AudioFunction.start_record(cb=freq_cb)

        while not self.stoprequest.isSet():
            time.sleep(0.1)

        AudioFunction.stop_audio()


class ToneDetector(object):
    WORK_THREADS = None

    class Event(object):
        TONE_DETECTED = "tone detected"
        TONE_MISSING = "tone missing"

    @staticmethod
    def start_listen(target_freq, cb, serialno=None, dclass=None, params={}):
        if ToneDetector.WORK_THREADS is None:
            ToneDetector.WORK_THREADS = {}

        th = None
        if serialno and dclass:
            th = dclass(serialno=serialno, target_freq=target_freq, callback=cb, **params)
            ToneDetector.WORK_THREADS["{}Hz".format(target_freq)] = th
        else:
            th = ToneDetectorForServerThread(target_freq=target_freq, callback=cb)
            ToneDetector.WORK_THREADS["{}Hz".format(target_freq)] = th

        if th != None:
            th.start()

    @staticmethod
    def stop_listen(target_freq=None):
        if target_freq != None and "{}Hz".format(target_freq) in ToneDetector.WORK_THREADS:
            th_name = "{}Hz".format(target_freq)
            ToneDetector.WORK_THREADS[th_name].join(timeout=10)
            del ToneDetector.WORK_THREADS[th_name]

            if len(ToneDetector.WORK_THREADS) > 0:
                return

        for th in ToneDetector.WORK_THREADS.values():
            th.join(timeout=10)
        ToneDetector.WORK_THREADS.clear()
        ToneDetector.WORK_THREADS = None


class DetectionStateListener(object):

    class Event(object):
        ACTIVE = "active"
        INACTIVE = "inactive"
        RISING_EDGE = "rising"
        FALLING_EDGE = "falling"

    def __init__(self, name=None):
        self.name = name
        self.daemon = True
        self.stoprequest = threading.Event()
        self.event_q = queue.Queue()
        self.current_event = None

    def get_tag(self):
        return "DetectionStateListener{}".format("::{}".format(self.name) if self.name else "")

    def clear(self):
        with self.event_q.mutex:
            self.event_q.queue.clear()
            self.current_event = None

    def reset(self):
        # reset function must consider the event handling:
        #   if the current state is not None, the active/inactive event might have been sent
        #   and such event should be sent again because it must be same with the case of None -> active
        #   so the active/inactive event needs to be sent again before setting the current state to None
        active_or_inactive = None
        with self.event_q.mutex:
            current_event = self.current_event
        if current_event:
            active_or_inactive = (
                DetectionStateListener.Event.ACTIVE
                if current_event[1] == ToneDetector.Event.TONE_DETECTED
                else DetectionStateListener.Event.INACTIVE
            )

        self.clear()

        if active_or_inactive:
            Logger.log(
                self.get_tag(), "reset and resend the event ({}, 0)".format(active_or_inactive)
            )
            self.event_q.put((active_or_inactive, 0))

    def tone_detected_event_cb(self, event):
        Logger.log(self.get_tag(), "tone_detected_event_cb: {}".format(event))
        self._handle_event(event)

    def _handle_event(self, event):
        active_or_inactive = (
            DetectionStateListener.Event.ACTIVE
            if event[1] == ToneDetector.Event.TONE_DETECTED
            else DetectionStateListener.Event.INACTIVE
        )

        self.event_q.put((active_or_inactive, 0))

        if self.current_event and self.current_event[1] != event[1]:
            rising_or_falling = (
                DetectionStateListener.Event.RISING_EDGE
                if event[1] == ToneDetector.Event.TONE_DETECTED
                else DetectionStateListener.Event.FALLING_EDGE
            )

            t2 = TimeUtils.time_from_str(event[0])
            t1 = TimeUtils.time_from_str(self.current_event[0])
            t_diff = t2 - t1
            self.event_q.put((rising_or_falling, t_diff.total_seconds() * 1000.0))

        self.current_event = event

    def wait_for_event(self, event, timeout):
        cnt = 0
        while cnt < timeout * 10:
            cnt += 1
            if self.stoprequest.isSet():
                return -1
            try:
                ev = self.event_q.get(timeout=0.1)
                Logger.log(self.get_tag(), "get event: {}".format(ev))
                if ev[0] == event:
                    return ev[1]
            except queue.Empty:
                with self.event_q.mutex:
                    current_event = self.current_event
                if current_event:
                    active_or_inactive = (
                        DetectionStateListener.Event.ACTIVE
                        if current_event[1] == ToneDetector.Event.TONE_DETECTED
                        else DetectionStateListener.Event.INACTIVE
                    )
                    if active_or_inactive == event:
                        Logger.log(
                            self.get_tag(),
                            "the current state '{}' fits the waited event".format(event),
                        )
                        return 0
        return -1
