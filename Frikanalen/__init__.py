# -*- coding: utf-8 -*-

import os
import datetime
import json
import getpass
import ConfigParser
import urllib2
import mechanize

class API:
    apiurl        = 'http://beta.frikanalen.no/api'
    if 'FRIKANALEN_DEV' in os.environ:
        apiurl        = 'http://frikanalen-dev.nuug.no/api'
    loginurl      = '%s/api-auth/login/?next=/api/' % apiurl
    videosurl     = '%s/videos' % apiurl
    videofilesurl = '%s/videofiles' % apiurl
    scheduleurl   = '%s/scheduleitems/' % apiurl
    tokenurl      = '%s/obtain-token' % apiurl

    mech     = None
    schedule = None
    username = None
    def __init__(self, debug = False):
        self.debug = debug
        self.mech = mechanize.Browser()
        if self.debug:
            self.mech.set_debug_http(True)

        self.schedule = Schedule(self)
        
    def load_config(self):
        config = ConfigParser.ConfigParser()
        configfilename = '~/.frikanalen.ini'
        config.read(os.path.expanduser(configfilename))

        if not config.has_section('auth'):
            print """
error: no %s or missing auth section in file.

The content of %s should look something like this:

[auth]
username=myusername
password=mypassword

""" % (configfilename, configfilename)
            exit(1)
        self.config = config

    def login(self, username = None, password = None):
        """
Log into Frikanalen using the provided username and password.  This is
required to gain access to privileged operations like writing schedule
and video entries.

The API and the django pages uses different login mechanisms, make
sure to log into both, as the API is not yet feature complete and we
need to use the django pages for some operations.

"""
        if username is None:
            self.load_config()
            username = self.config.get('auth', 'username')
        if password is None:
            self.load_config()
            try:
                password = self.config.get('auth', 'password')
            except ConfigParser.NoOptionError:
                password = getpass.getpass("Password for %s: " % username)

        # Django login
        res = self.mech.open(self.loginurl)
        self.mech.select_form(nr=0);
        self.mech['username'] = username
        self.mech['password'] = password
        response = self.mech.submit()

        self.mech.open(self.tokenurl)
        jsonstr = self.mech.response().read()
        j = json.loads(jsonstr.decode('utf8'))
#        print j
        token = j[u'key']
        self.extraheaders = [('Authorization', 'Token %s' % token)]
        self.mech.addheaders = self.extraheaders

        # Document that we are logged in as a user
        self.username = username

    def video_find(self, video_id = None, query = None):
        if video_id is not None:
            v = Video(self, video_id)
            return [v]

        if query is not None:
            url = '%s/?page_size=10000&q=%s' % (self.videosurl, query)
#            print url
            self.mech.open(url)
            jsonstr = self.mech.response().read()
            videos = []
            for v in json.loads(jsonstr.decode('utf8'))['results']:
                videos.append(Video(self,v['id']))
            return videos

    def json_post(self, url, jsondata):
        """
Post JSON data to the API.

Tried to use mechanize, but did not find a way to set content-type
with POST request.  Using urllib2 until I find a way to do it.

"""
        json_data = json.dumps(jsondata)
        headers = {
            'Content-type': 'application/json; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With' : 'XMLHttpRequest'
            }
#        print headers
        for tup in self.extraheaders:
            headers[tup[0]] = tup[1]
        req = urllib2.Request(url, data = json_data, headers = headers)
        f = urllib2.urlopen(req)
        # FIXME check return value
        return f

class Schedule:
    scheduledata = []
    def __init__(self, frikanalen):
        self.frikanalen = frikanalen
    def load_around(self, timestamp):
        """
Load all schedule items around the given time stamp.

The timestamp argument should be a datetime.datetime object.
"""
        url = '%s?surrounding=1&days=1&date=%s' % (
            self.frikanalen.scheduleurl, timestamp.strftime("%Y%m%d")
            )
#        print url
        self.frikanalen.mech.open(url)
        jsonstr = self.frikanalen.mech.response().read()
        j = json.loads(jsonstr.decode('utf8'))
#        print j
        if j['count'] != len(j['results']):
            raise Exception("incorrect length in scheduleitems result")
        self.scheduledata = j['results']

        # Add placeholder far off in the future
        # Workaround for while loop in insert() not working when
        # inserting after the last item in the list.
        self.scheduledata.append({
                        "default_name":"",
                        "duration": "0",
                        "schedulereason": 4,
                        "starttime":"9000-01-01T00:00:00Z",
                        "display_name": ""
                        })

    def insert(self, video, starttime):
#        print "Called Schedule.insert()"

        if starttime < datetime.datetime.now():
            raise Exception("Not possible to schedule in the past")

        self.load_around(starttime)
#        print self.scheduledata
        i = 0
        lastend = None
        while i < len(self.scheduledata):
            f = self.scheduledata[i]
#            print f
            fduration = Video.duration2timedelta(f['duration'])
            fstarttime = Video.start2datetime(f['starttime'])

            if lastend is not None:
                gap = fstarttime - lastend
#                print "Gap:", gap
#            print fstarttime, fduration, starttime, video.duration()
            endtime = starttime + video.duration()
            
            if lastend is not None and endtime < fstarttime:
                if lastend < starttime:
#                    print "Found free spot"
                    sentitem = {
                        "default_name"    : "",
                        "display_name"    : video.name(),
                        "duration"        : str(video.duration()),
                        # 3 = User reason
                        # 4 = Automatic reason
                        "schedulereason"  : 3,
                        "video_id"        :
                            "http://localhost:8000/api/videos/%d" % video.id,
                        "starttime"       : starttime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        }
                    self.frikanalen.json_post(self.frikanalen.scheduleurl, sentitem)
                    return True
                else:
                    raise Exception("no free spot in schedule at that time")
            lastend = fstarttime + fduration
            i += 1
        return False

    def free_slots_between(self, starttime, endtime, minduration=datetime.timedelta(0)):
        """
Return a list of free slot at or after starttime, and before endtime.

FIXME need to implemnt filtering using starttime and endtime.
"""
        url = '%s?date=%s&days=%s&page_size=1000' % (
            self.frikanalen.scheduleurl,
            starttime.strftime("%Y%m%d"),
            (endtime - starttime).days
            )
        print url
        self.frikanalen.mech.open(url)
        jsonstr = self.frikanalen.mech.response().read()
        j = json.loads(jsonstr.decode('utf8'))
        print j
        if j['count'] != len(j['results']):
            raise Exception("incorrect length in scheduleitems result, got %d not %d" % (len(j['results']), j['count']))
        freeslots = []
        lastvend = None
        for entry in j['results']:
            vstart = Video.start2datetime(entry['starttime'])
            vdur = Video.duration2timedelta(entry['duration'])
            vend = vstart + vdur
            print vstart, vdur, vend
            # FIXME limit to the time range requested
            if lastvend is not None:
                vhole = vstart - lastvend
                if minduration <= vhole:
                    print minduration, '<', vdur
                    freeslots.append({'start' : lastvend,
                                      'end' : vstart,
                                      'duration' : vhole })

            lastvend = vend
        return freeslots

class Video:
    def __init__(self, frikanalen, video_id):
        self.frikanalen = frikanalen
        self.id = video_id
        self.meta = {}
        self._load_info()

    def _load_info(self):
        self.frikanalen.mech.open('%s/%d' % (self.frikanalen.videosurl, self.id))
        jsonstr = self.frikanalen.mech.response().read()

        # FIXME move meta hash into member attributes?
        self.meta = json.loads(jsonstr.decode('utf8'))

    @staticmethod
    def start2datetime(timestamp):
        return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def duration2timedelta(duration):
        s = 0.0
        for part in duration.split(':'):
            s *= 60.0
            s += float(part)
        return datetime.timedelta(0, s)

    def duration(self):
        """
Return video duration as a datetime.timedelta.
"""
        return Video.duration2timedelta(self.meta['duration'])
    def duration_as_timedelta(self):
        return self.duration2timedelta(self.duration())
    def name(self):
        return self.meta['name']
    def __repr__(self):
        return str({'id' : self.id, 'meta': self.meta})
    def __str__(self):
        return self.__repr__()
