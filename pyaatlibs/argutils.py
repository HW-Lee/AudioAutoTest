import getopt


class AATArgParseUtils(object):

    @staticmethod
    def parse_arg(argv, options, required=[]):
        opts, args = getopt.getopt(argv, "", options)

        argv = [(opt[0][2:], opt[1]) for opt in opts if opt[0].startswith("--")]
        argv = dict(argv)
        for key in required:
            if not key in argv:
                return (False, RuntimeError("parameter <{}> is required".format(key)))

        return (True, argv)
