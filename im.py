class PersonalInfo:
    def __init__(self):
        self.yahoo_id = ''      # our Yahoo! ID
        self.name = ''          # Real name
        self.surname = ''       # Real surname
        self.country = ''       # Country ID


class Contact:
    def __init__(self):
        self.id             = ''
        self.yahoo_id       = ''
        self.nickname       = ''
        self.fname          = ''
        self.mname          = ''
        self.lname          = ''
        self.email          = ''
        self.email1         = ''
        self.email2         = ''
        self.mobile         = ''
        self.msnid          = ''
        self.note1          = ''
        self.note2          = ''
        self.note3          = ''
        self.note4          = ''
        self.home_addr      = ''
        self.home_city      = ''
        self.home_state     = ''
        self.home_zip       = ''
        self.home_country   = ''
        self.home_phone     = ''
        self.work_company   = ''
        self.work_addr      = ''
        self.work_city      = ''
        self.work_state     = ''
        self.work_zip       = ''
        self.work_country   = ''
        self.work_phone     = ''
        self.birthday       = ''
        self.anniversary    = ''
        self.note           = ''
        self.fax            = ''
        self.skype          = ''
        self.other_phone    = ''
        self.pager          = ''
        self.website        = ''
        self.job_title      = ''
        self.work_website   = ''


class Buddy:
    def __init__(self):
        self.yahoo_id = ''          # buddy's Yahoo! ID
        self.status   = Status()    # buddy Status
        self.settings = Settings()  # buddy's settings (only for self-buddy)
        self.contact  = Contact()   # Contact()
        self.ignored  = False       # buddy is on ignore list
        self.pending  = False       # buddy is pending add request confirmation

    def __repr__(self):
        return '<Buddy: "{0}">'.format(self.yahoo_id)


class Group:
    def __init__(self):
        self.name = ''          # group name
        self.buddies = []       # a list of Buddy

    def __repr__(self):
        return '<Group: "{0}", count: {1}>'.format(self.name, len(self.buddies))


class Status:
    def __init__(self):
        self.online = False
        self.availability = 0
        self.code = 0x00
        self.message = ''
        self.idle_time = 0


class TypingNotify:
    def __init__(self):
        self.sender = ''        # buddy's Yahoo! ID
        self.receiver = ''      # usually our ID
        self.status = 0         # 0 - stopped; 1 - started


class PersonalMessage:
    def __init__(self):
        self.offline = False    # is offline message?
        self.sender = ''
        self.receiver = ''
        self.timestamp = ''
        self.message = ''
        self.id = ''


class Settings:
    def __init__(self):
        self.skin = ''
        self.show_insider = False
        self.autologin = False
        self.hiddenlogin = False


class AddRequest:
    def __init__(self):
        self.sender = ''
        self.yahoo_id = ''
        self.group = ''
        self.message = ''
        self.fname = ''
        self.lname = ''
        self.service = 1


class AddRequestResponse:
    def __init__(self):
        self.sender = ''
        self.yahoo_id = ''
        self.group = ''
        self.success = False


class BuddyAuthorization:
    def __init__(self):
        self.sender = ''
        self.receiver = ''
        self.response = 0
        self.fname = ''
        self.lname = ''
        self.message = ''


class RemoveBuddy:
    def __init__(self):
        self.sender = ''
        self.yahoo_id = ''
        self.group = ''


class MoveBuddy:
    def __init__(self):
        self.sender = ''
        self.yahoo_id = ''
        self.from_group = ''
        self.to_group = ''


class Audible:
    @property
    def base_url(self):
        return 'http://l.yimg.com/pu/dl/aud/'

    def __init__(self):
        self.sender = ''
        self.receiver = ''
        self.url = ''
        self.name = ''
        self.message = ''
        self.checksum = ''
