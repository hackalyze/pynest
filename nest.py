#! /usr/bin/python

# nest.py -- a python interface to the Nest Thermostat
# by Scott M Baker, smbaker@gmail.com, http://www.smbaker.com/
#
# Usage:
#    'nest.py help' will tell you what to do and how to do it
#
# Licensing:
#    This is distributed unider the Creative Commons 3.0 Non-commecrial,
#    Attribution, Share-Alike license. You can use the code for noncommercial
#    purposes. You may NOT sell it. If you do use it, then you must make an
#    attribution to me (i.e. Include my name and thank me for the hours I spent
#    on this)
#
# Acknowledgements:
#    Chris Burris's Siri Nest Proxy was very helpful to learn the nest's
#       authentication and some bits of the protocol.
#
# Update 1/18/2015 -- Chris Pawlukowsky, https://github.com/hackalyze
#    Minor update to fix a urllib2 SSL protocol error and to add support
#    for setting away mode.  Also some cleanup and PEP8.

import functools
import urllib
import urllib2
import ssl
import sys
import time
from optparse import OptionParser

##########################################################
# Hack to force TLSv1 to prevent urllib2 from throwing a URLError of
# "EOF occurred in violation of protocol" when making a request to Nest.
# http://askubuntu.com/questions/116020/python-https-requests-urllib2-to-some-sites-fail-on-ubuntu-12-04-without-proxy

old_init = ssl.SSLSocket.__init__


@functools.wraps(old_init)
def fix_ssl(self, *args, **kwargs):
    kwargs['ssl_version'] = ssl.PROTOCOL_TLSv1
    old_init(self, *args, **kwargs)


ssl.SSLSocket.__init__ = fix_ssl

#########################################################

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        print ("No json library available. "
               "I recommend installing either python-json "
               "or simpejson.")
        sys.exit(-1)


class Nest(object):
    def __init__(self, username, password, serial=None, index=0, units="F"):
        self.username = username
        self.password = password
        self.serial = serial
        self.units = units
        self.index = index

    @staticmethod
    def loads(res):
        if hasattr(json, "loads"):
            res = json.loads(res)
        else:
            res = json.read(res)
        return res

    def make_request(self, url, data=None):
        req = urllib2.Request('%s/v2/%s' % (self.transport_url, url), data,
                              headers=self.headers)
        return urllib2.urlopen(req).read()

    def login(self):
        data = urllib.urlencode({
            "username": self.username,
            "password": self.password}
        )
        req = urllib2.Request(
            "https://home.nest.com/user/login",
            data,
            {"user-agent": "Nest/1.1.0.10 CFNetwork/548.0.4"}
        )
        res = urllib2.urlopen(req).read()
        res = self.loads(res)
        self.transport_url = res["urls"]["transport_url"]
        self.access_token = res["access_token"]
        self.userid = res["userid"]
        self.headers = {"user-agent": "Nest/1.1.0.10 CFNetwork/548.0.4",
                        "Authorization": "Basic " + self.access_token,
                        "X-nl-user-id": self.userid,
                        "X-nl-protocol-version": "1"}

    def get_status(self):
        res = self.make_request('mobile/user.%s' % self.userid)
        res = self.loads(res)
        self.structure_id = res["structure"].keys()[0]
        if (self.serial is None):
            structure = res["structure"][self.structure_id]
            self.device_id = structure["devices"][self.index]
            self.serial = self.device_id.split(".")[1]
        self.status = res

    def show_status(self):
        shared = self.status["shared"][self.serial]
        device = self.status["device"][self.serial]
        allvars = shared
        allvars.update(device)
        for k in sorted(allvars.keys()):
            print k + "." * (32 - len(k)) + ":", allvars[k]

    def temp_in(self, temp):
        if self.units == "F":
            return (temp - 32.0) / 1.8
        else:
            return temp

    def temp_out(self, temp):
        if self.units == "F":
            return (temp * 1.8) + 32.0
        else:
            return temp

    def show_curtemp(self):
        temp = self.status["shared"][self.serial]["current_temperature"]
        temp = self.temp_out(temp)
        print "%0.1f" % temp

    def set_temperature(self, temp):
        temp = self.temp_in(temp)
        data = json.dumps({
            'target_change_pending': True,
            'target_temperature': '%0.1f' % temp
        })
        print self.make_request('put/shared.%s' % self.serial, data)

    def set_away(self, away=False):
        data = json.dumps({
            'away_timestamp': int(time.time()),
            'away': True if away else False,
            'away_setter': 0
        })
        print self.make_request('put/structure.%s' % self.structure_id, data)

    def set_fan(self, state):
        data = json.dumps({'fan_mode': str(state)})
        print self.make_request('put/device.%s' % self.serial, data)


def create_parser():
    parser = OptionParser(
        usage="nest [options] command [command_options] [command_args]",
        description="Commands: fan temp",
        version="unknown"
    )

    parser.add_option("-u", "--user", dest="user",
                      help="username for nest.com", metavar="USER", default=None)

    parser.add_option("-p", "--password", dest="password",
                      help="password for nest.com", metavar="PASSWORD", default=None)

    parser.add_option("-c", "--celsius", dest="celsius", action="store_true", default=False,
                      help="use celsius instead of farenheit")

    parser.add_option("-s", "--serial", dest="serial", default=None,
                      help="optional, specify serial number of nest thermostat to talk to")

    parser.add_option("-i", "--index", dest="index", default=0, type="int",
                      help="optional, specify index number of nest to talk to")
    return parser


def help():
    print "syntax: nest [options] command [command_args]"
    print "options:"
    print "   --user <username>      ... username on nest.com"
    print "   --password <password>  ... password on nest.com"
    print "   --celsius              ... use celsius (the default is farenheit)"
    print "   --serial <number>      ... optional, specify serial number of nest to use"
    print "   --index <number>       ... optional, 0-based index of nest"
    print "                                (use --serial or --index, but not both)"
    print
    print "commands: temp, fan, show, curtemp, curhumid"
    print "    temp <temperature>    ... set target temperature"
    print "    fan [auto|on]         ... set fan state"
    print "    show                  ... show everything"
    print "    curtemp               ... print current temperature"
    print "    curhumid              ... print current humidity"
    print
    print "examples:"
    print "    nest.py --user joe@user.com --password swordfish temp 73"
    print "    nest.py --user joe@user.com --password swordfish fan auto"


def main():
    parser = create_parser()
    opts, args = parser.parse_args()

    if len(args) == 0 or args[0] == "help":
        help()
        sys.exit(-1)

    if not opts.user or not opts.password:
        print "how about specifying a --user and --password option next time?"
        sys.exit(-1)

    if opts.celsius:
        units = "C"
    else:
        units = "F"

    n = Nest(opts.user, opts.password, opts.serial, opts.index, units=units)
    n.login()
    n.get_status()

    cmd = args[0]

    if cmd == "temp":
        if len(args) < 2:
            print "please specify a temperature"
            sys.exit(-1)
        n.set_temperature(int(args[1]))
    elif cmd == "fan":
        if len(args) < 2:
            print "please specify a fan state of 'on' or 'auto'"
            sys.exit(-1)
        n.set_fan(args[1])
    elif cmd == "show":
        n.show_status()
    elif cmd == "curtemp":
        n.show_curtemp()
    elif cmd == "curhumid":
        print n.status["device"][n.serial]["current_humidity"]
    else:
        print "misunderstood command:", cmd
        print "do 'nest.py help' for help"


if __name__ == "__main__":
    main()
