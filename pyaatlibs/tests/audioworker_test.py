import pytest
from unittest.mock import MagicMock

import re
import time
import packaging.version

import pyaatlibs
from pyaatlibs.audioworker import AudioWorkerApp, RecordPerf, RecordApi, RecordInputSrc
try:
    from pyaatlibs.audioworker import TaskIndex
except:
    class TaskIndex:
        ALL = -1

from pyaatlibs.adbutils import Adb

SHORT_SHA_FMT = "[0-9a-f]{7,40}"
VERSION_FMT = "\\d+(\\.\\d+)*"

@pytest.fixture(scope="session")
def apk_path(pytestconfig):
    return pytestconfig.getoption("apk_path")

@pytest.fixture(scope="session")
def serialno(pytestconfig):
    return pytestconfig.getoption("serialno")

@pytest.fixture(scope="session")
def target_version():
    return AudioWorkerApp.get_apk_version()

@pytest.fixture(scope="session")
def skip_version_check(pytestconfig):
    return pytestconfig.getoption("skip_version_check")

@pytest.fixture(scope="session")
def skip_function_check(pytestconfig):
    return pytestconfig.getoption("skip_function_check")

@pytest.fixture(scope="session")
def dut_info_provided(serialno):
    return all([serialno])

@pytest.fixture(scope="session")
def check_options(pytestconfig):
    required_options = [
        "serialno"
    ]

    # It only allows that all required parameters being specified or kept empty
    if not any(map(pytestconfig.getoption, required_options)):
        return

    for ropt in required_options:
        assert pytestconfig.getoption(ropt) is not None

def intersect_dict(d1, d2):
    intersection = {}
    for k in d1.keys() & d2.keys():
        if isinstance(d1[k], dict) ^ isinstance(d2[k], dict):
            continue

        # If they both are dicts, only intersection of them will be kept
        if isinstance(d1[k], dict):
            intersection[k] = intersect_dict(d1[k], d2[k])

        # Otherwise, only equivalent value will be kept
        elif d1[k] == d2[k]:
            intersection[k] = d1[k]

    return intersection

def test_intersect_dict():
    assert intersect_dict({"a": 1}, {"b": 1}) == {}
    assert intersect_dict({"a": 1, "c": 3}, {"b": 1}) == {}
    assert intersect_dict({"a": 1, "c": 3}, {"b": 1, "c": 3}) == {"c": 3}
    assert intersect_dict({"a": 1, "c": 3}, {"b": 1, "c": 3}) == {"c": 3}
    assert intersect_dict({"a": 1, "c": 3}, {"b": 1, "c": 2}) == {}
    assert intersect_dict(
        {
            "a": 1,
            "c": {
                "a": 1
            }
        },
        {
            "b": 1,
            "c": 3
        }) == {}
    assert intersect_dict(
        {
            "a": 1,
            "c": {
                "a": 1
            }
        },
        {
            "b": 1,
            "c": {
                "a": 1
            }
        }) == {
            "c": {
                "a": 1
            }
        }
    assert intersect_dict(
        {
            "a": 1,
            "c": {
                "a": 1
            }
        },
        {
            "b": 1,
            "c": {
                "a": 2
            }
        }) == {
            "c": {}
        }

def is_subdict(smaller, larger):
    return intersect_dict(smaller, larger) == smaller

def assert_if_not_subdict(smaller, larger):
    assert intersect_dict(smaller, larger) == smaller

def test_is_subdict():
    assert is_subdict({}, {})
    assert is_subdict({}, {"a": 1})
    assert is_subdict({"b": 1}, {"a": 1, "b": 1})
    assert not is_subdict({"b": 1, "c": 1}, {"a": 1, "b": 1})
    assert is_subdict({"b": {"a": 1}}, {"a": 1, "b": {"a": 1, "b": 1}})
    assert not is_subdict({"b": {"a": 1}}, {"a": 1, "b": {}})
    assert not is_subdict({"b": {"a": 1}}, {"a": 1, "b": {"a": 2}})

def test_install(check_options, serialno, apk_path):
    if not any([serialno, apk_path]):
        pytest.skip("The information of DuT is not provided.")

    if apk_path is not None:
        AudioWorkerApp.get_apk_path = MagicMock(return_value=apk_path)

    if AudioWorkerApp.installed(serialno=serialno):
        AudioWorkerApp.uninstall(serialno=serialno)

    AudioWorkerApp.install(serialno=serialno, grant=True)
    assert AudioWorkerApp.installed(serialno=serialno)

def test_apk_version(check_options, target_version, serialno, skip_version_check):
    if not any([target_version, serialno]):
        pytest.skip("The information of DuT is not provided.")

    if skip_version_check:
        pytest.skip("The version check is skipped.")

    apk_version = AudioWorkerApp.get_version_from_device(serialno=serialno)
    assert len(apk_version) > 0

    vname_fmt = "(?P<commit_sha>{})\\-python\\-audio\\-autotest\\-v(?P<pyaat_version>{})$".format(
        SHORT_SHA_FMT, VERSION_FMT)

    m = re.match(vname_fmt, apk_version)
    assert m is not None, "The version name '{}' is not valid.".format(out.strip())
    assert apk_version == target_version

def wait_for_activities(serialno, func, onset=True):
    retry = 10
    while retry > 0:
        if bool(func(serialno=serialno)) == onset:
            return True

        retry -= 1
        time.sleep(1)

    return False

def wait_for_playback_activities(serialno, onset=True):
    return wait_for_activities(serialno, AudioWorkerApp.playback_info, onset)

def wait_for_record_activities(serialno, onset=True, task_index=TaskIndex.ALL):
    try:
        pyaatlibs.__version__
        func = lambda serialno: AudioWorkerApp.record_info(
            serialno=serialno, task_index=task_index)
    except:
        func = AudioWorkerApp.record_info

    return wait_for_activities(serialno, func, onset)

def prepare_app(serialno):
    AudioWorkerApp.relaunch_app(serialno=serialno)
    time.sleep(3)

def run_general_single_playback(serialno, playback_type):
    prepare_app(serialno=serialno)

    FUNCTIONS = {
        "non-offload": AudioWorkerApp.playback_nonoffload,
        "offload": AudioWorkerApp.playback_offload,
        "low-latency": AudioWorkerApp.playback_nonoffload,
    }

    DEFAULT_CONFIGS = {
        "non-offload": {
            "serialno": serialno,
        },
        "offload": {
            "serialno": serialno,
        },
        "low-latency": {
            "serialno": serialno,
            "low_latency_mode": True,
        }
    }

    playback_func = FUNCTIONS[playback_type]
    cfg = DEFAULT_CONFIGS[playback_type]

    if playback_type == "low-latency":
        playback_type = "non-offload"

    # Default test
    playback_func(**cfg)
    assert wait_for_playback_activities(serialno=serialno)
    assert_if_not_subdict({
        playback_type: {
            "0": {
                "class": "com.google.audioworker.functions.audio.playback.PlaybackStartFunction",
                "has-ack": False,
                "params": {
                    "type": playback_type,
                    "target-freqs": "440.0",
                    "playback-id": 0,
                    "low-latency-mode": "low_latency_mode" in cfg and cfg["low_latency_mode"],
                    "amplitude": 0.6,
                    "sampling-freq": 16000,
                    "num-channels": 2,
                    "pcm-bit-width": 16
                }
            }
        }
    }, AudioWorkerApp.playback_info(serialno=serialno))

    AudioWorkerApp.playback_stop(serialno=serialno)
    assert wait_for_playback_activities(serialno=serialno, onset=False)

    # Specifying playback id
    playback_func(**cfg, playback_id=1)
    assert wait_for_playback_activities(serialno=serialno)
    assert_if_not_subdict({
        playback_type: {
            "1": {
                "class": "com.google.audioworker.functions.audio.playback.PlaybackStartFunction",
                "has-ack": False,
                "params": {
                    "type": playback_type,
                    "target-freqs": "440.0",
                    "playback-id": 1,
                    "low-latency-mode": "low_latency_mode" in cfg and cfg["low_latency_mode"],
                    "amplitude": 0.6,
                    "sampling-freq": 16000,
                    "num-channels": 2,
                    "pcm-bit-width": 16
                }
            }
        }
    }, AudioWorkerApp.playback_info(serialno=serialno))

    AudioWorkerApp.playback_stop(serialno=serialno)
    assert wait_for_playback_activities(serialno=serialno, onset=False)

    # Dual frequencies playback
    playback_func(**cfg, freqs=[440, 442])
    assert wait_for_playback_activities(serialno=serialno)
    assert_if_not_subdict({
        playback_type: {
            "0": {
                "class": "com.google.audioworker.functions.audio.playback.PlaybackStartFunction",
                "has-ack": False,
                "params": {
                    "type": playback_type,
                    "target-freqs": "440,442",
                    "playback-id": 0,
                    "low-latency-mode": "low_latency_mode" in cfg and cfg["low_latency_mode"],
                    "amplitude": 0.6,
                    "sampling-freq": 16000,
                    "num-channels": 2,
                    "pcm-bit-width": 16
                }
            }
        }
    }, AudioWorkerApp.playback_info(serialno=serialno))

    # Stop
    AudioWorkerApp.playback_stop(serialno=serialno)
    assert wait_for_playback_activities(serialno=serialno, onset=False)

def test_single_nonoffload_playback(check_options, target_version, skip_function_check, serialno):
    if not any([target_version, serialno]):
        pytest.skip("The information of DuT is not provided.")

    if skip_function_check:
        pytest.skip("The function check is skipped.")

    run_general_single_playback(serialno=serialno, playback_type="non-offload")

def test_single_offload_playback(check_options, target_version, skip_function_check, serialno):
    if not any([target_version, serialno]):
        pytest.skip("The information of DuT is not provided.")

    if skip_function_check:
        pytest.skip("The function check is skipped.")

    run_general_single_playback(serialno=serialno, playback_type="offload")

def test_single_low_latency_playback(check_options, target_version, skip_function_check, serialno):
    if not any([target_version, serialno]):
        pytest.skip("The information of DuT is not provided.")

    if skip_function_check:
        pytest.skip("The function check is skipped.")

    run_general_single_playback(serialno=serialno, playback_type="low-latency")

def manipulate_detector_handle_names(detectors_dict):
    keys = sorted(list(detectors_dict))
    idx = 0
    for k in keys:
        serialized_name = "detector#{}".format(idx)
        detectors_dict[serialized_name] = detectors_dict[k]
        detectors_dict[serialized_name]["Handle"] = serialized_name
        idx += 1

    for k in keys:
        del detectors_dict[k]

DEFAULT_DUMP_MS = {
    "default": 1000,
    "1.4.3": 0
}
def test_single_record(check_options, target_version, skip_function_check, serialno):
    if not any([target_version, serialno]):
        pytest.skip("The information of DuT is not provided.")

    if skip_function_check:
        pytest.skip("The function check is skipped.")

    dump_buffer_ms = DEFAULT_DUMP_MS["default"] \
        if not target_version in DEFAULT_DUMP_MS else DEFAULT_DUMP_MS[target_version]

    prepare_app(serialno=serialno)

    # Default start
    AudioWorkerApp.record_start(serialno=serialno)
    assert wait_for_record_activities(serialno=serialno)
    ans = [
        # The record track's information
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": dump_buffer_ms,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 0,
                "audio-perf": 10
            }
        },
        # The detectors' information
        {}
    ]
    for a, b in zip(ans, AudioWorkerApp.record_info(serialno=serialno)):
        import json
        print(json.dumps(a, indent=2))
        print(json.dumps(b, indent=2))
        assert_if_not_subdict(a, b)

    return

    # Detector registration
    AudioWorkerApp.record_detector_register(
        serialno=serialno, dclass="ToneDetector", params={"target-freq": [440]})
    info = AudioWorkerApp.record_info(serialno=serialno)

    # It's composed of the track's and its detectors' information packed in dicts
    assert len(info) == 2 and all(map(lambda x: isinstance(x, dict), info))

    assert_if_not_subdict({
        "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
        "has-ack": False,
        "params": {
            "sampling-freq": 16000,
            "num-channels": 2,
            "pcm-bit-width": 16,
            "dump-buffer-ms": dump_buffer_ms,
            "btsco-on": True,
            "input-src": 1,
            "audio-api": 0,
            "audio-perf": 10
        }
    }, info[0])

    # It should contain exactly 1 detector and the handle name should be in the form like:
    #   com.google.audioworker.functions.audio.record.detectors.ToneDetector@18fad39
    class_name = "com.google.audioworker.functions.audio.record.detectors.ToneDetector"
    detector_handle_fmt = class_name + "@[0-9a-f]{7}"
    assert len(info[1]) == 1 and all(map(lambda x: re.match(detector_handle_fmt, x), info[1]))

    manipulate_detector_handle_names(info[1])
    ans = [
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": dump_buffer_ms,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 0,
                "audio-perf": 10
            }
        },
        {
            "detector#0": {
                "Handle": "detector#0",
                "Sampling Frequency": 16000,
                "Process Frame Size": 50,
                "Tolerance (semitone)": 1,
                "unit": {
                    "Sampling Frequency": "Hz",
                    "Process Frame Size": "ms",
                    "Tolerance (semitone)": "keys"
                },
                "Targets": [
                    {
                        "target-freq": 440
                    }
                ]
            }
        }
    ]
    for a, b in zip(ans, info):
        assert_if_not_subdict(a, b)

    # Multiple detectors registration
    AudioWorkerApp.record_detector_register(
        serialno=serialno, dclass="ToneDetector", params={"target-freq": [442]})
    info = AudioWorkerApp.record_info(serialno=serialno)

    # It's composed of the track's and its detectors' information packed in dicts
    assert len(info) == 2 and all(map(lambda x: isinstance(x, dict), info))

    # It should contain exactly 1 detector and the handle name should be in the form like:
    #   com.google.audioworker.functions.audio.record.detectors.ToneDetector@18fad39
    class_name = "com.google.audioworker.functions.audio.record.detectors.ToneDetector"
    detector_handle_fmt = class_name + "@[0-9a-f]{7}"
    assert len(info[1]) == 2 and all(map(lambda x: re.match(detector_handle_fmt, x), info[1]))

    manipulate_detector_handle_names(info[1])
    ans = [
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": dump_buffer_ms,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 0,
                "audio-perf": 10
            }
        },
        {
            "detector#0": {
                "Handle": "detector#0",
                "Sampling Frequency": 16000,
                "Process Frame Size": 50,
                "Tolerance (semitone)": 1,
                "unit": {
                    "Sampling Frequency": "Hz",
                    "Process Frame Size": "ms",
                    "Tolerance (semitone)": "keys"
                },
                "Targets": [
                    {
                        "target-freq": 442
                    }
                ]
            },
            "detector#1": {
                "Handle": "detector#1",
                "Sampling Frequency": 16000,
                "Process Frame Size": 50,
                "Tolerance (semitone)": 1,
                "unit": {
                    "Sampling Frequency": "Hz",
                    "Process Frame Size": "ms",
                    "Tolerance (semitone)": "keys"
                },
                "Targets": [
                    {
                        "target-freq": 440
                    }
                ]
            }
        }
    ]
    for a, b in zip(ans, info):
        assert_if_not_subdict(a, b)

    # Stop
    AudioWorkerApp.record_stop(serialno=serialno)
    assert wait_for_record_activities(serialno=serialno, onset=False)

def test_concurrent_record(check_options, target_version, skip_function_check, serialno):
    if packaging.version.parse(target_version.split("-")[-1]) < packaging.version.parse("1.5"):
        pytest.skip("This is only for PyAAT later than v1.5")

    if skip_function_check:
        pytest.skip("The function check is skipped.")

    # Default start
    AudioWorkerApp.record_start(serialno=serialno, task_index=0)
    AudioWorkerApp.record_start(serialno=serialno, task_index=1)
    assert wait_for_record_activities(serialno=serialno, task_index=0)
    assert wait_for_record_activities(serialno=serialno, task_index=1)

    ans = [
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": 1000,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 0,
                "audio-perf": 10,
                "task-index": 0
            }
        },
        {},
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": 1000,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 0,
                "audio-perf": 10,
                "task-index": 1
            }
        },
        {}
    ]
    for a, b in zip(ans, AudioWorkerApp.record_info(serialno=serialno)):
        assert_if_not_subdict(a, b)

    # Stop
    AudioWorkerApp.record_stop(serialno=serialno)
    assert wait_for_record_activities(serialno=serialno, onset=False)

    # Different configurations
    AudioWorkerApp.record_start(
        serialno=serialno, task_index=0,
        input_src=RecordInputSrc.MIC, api=RecordApi.OPENSLES, perf=RecordPerf.POWER_SAVING)
    AudioWorkerApp.record_start(
        serialno=serialno, task_index=1,
        input_src=RecordInputSrc.CAMCORDER, api=RecordApi.AAUDIO, perf=RecordPerf.LOW_LATENCY)
    assert wait_for_record_activities(serialno=serialno, task_index=0)
    assert wait_for_record_activities(serialno=serialno, task_index=1)

    ans = [
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": 1000,
                "btsco-on": True,
                "input-src": 1,
                "audio-api": 1,
                "audio-perf": 11,
                "task-index": 0
            }
        },
        {},
        {
            "class": "com.google.audioworker.functions.audio.record.RecordStartFunction",
            "has-ack": False,
            "params": {
                "sampling-freq": 16000,
                "num-channels": 2,
                "pcm-bit-width": 16,
                "dump-buffer-ms": 1000,
                "btsco-on": True,
                "input-src": 5,
                "audio-api": 2,
                "audio-perf": 12,
                "task-index": 1
            }
        },
        {}
    ]
    for a, b in zip(ans, AudioWorkerApp.record_info(serialno=serialno)):
        assert_if_not_subdict(a, b)

def test_uninstall(check_options, serialno):
    if not any([serialno]):
        pytest.skip("The information of DuT is not provided.")

    assert AudioWorkerApp.installed(serialno=serialno)
    AudioWorkerApp.uninstall(serialno=serialno)
    assert not AudioWorkerApp.installed(serialno=serialno)
