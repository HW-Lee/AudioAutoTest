import datetime
import json
from pyaatlibs.timeutils import TimeUtils

try:
    import functools

    reduce = functools.reduce
except ImportError:
    pass


class TrialHelper(object):

    @staticmethod
    def _check_type(trials):
        if not isinstance(trials, list):
            raise ValueError("The input must be an instance of list")
        if len(trials) > 0 and not reduce(
            lambda x, y: x & y, map(lambda trial: isinstance(trial, Trial), trials)
        ):
            raise ValueError("The input contains elements which are not instances of Trial")

    @staticmethod
    def _pass_fail_check(trial):
        return trial.is_pass()

    @staticmethod
    def load(filename):
        with open(filename, "r") as f:
            jsonobjs = json.load(f)

        trials = []
        for jsonobj in jsonobjs:
            trial = Trial()
            trial.ds = jsonobj
            trials.append(trial)

        return trials

    @staticmethod
    def categorize_in(trials, cat_func):
        TrialHelper._check_type(trials)
        trials_cat = {}
        for trial in trials:
            key = cat_func(trial)
            if not key in trials_cat.keys():
                trials_cat[key] = []

            trials_cat[key].append(trial)

        return trials_cat

    @staticmethod
    def to_json(trials):
        TrialHelper._check_type(trials)
        return json.dumps(list(map(lambda trial: trial.ds, trials)), indent=4, ensure_ascii=False)

    @staticmethod
    def pass_fail_list(trials, check_func=None):
        TrialHelper._check_type(trials)
        if not check_func:
            check_func = TrialHelper._pass_fail_check
        return map(check_func, trials)


class Trial(object):

    def __init__(self, taskname=None, pass_check=None):
        self.ds = {
            "task": taskname,
            "timestamp": TimeUtils.now_str(),
            "status": "valid",
            "error-msg": None,
        }
        self.pass_check = pass_check

    def is_valid(self):
        return self.ds["status"] == "valid"

    def is_pass(self):
        if not self.is_pass:
            raise ValueError("The pass/fail check function has not been defined")
        return self.pass_check(self)

    def put_extra(self, name, value):
        if not "extra" in self.ds.keys():
            self.ds["extra"] = {}

        self.ds["extra"][name] = value

    def invalidate(self, errormsg):
        self.ds["status"] = "invalid"
        self.ds["error-msg"] = errormsg
