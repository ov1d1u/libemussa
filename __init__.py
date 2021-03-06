import socket, urllib.parse, urllib.request, threading, time
import os
import queue
from collections import OrderedDict
from random import choice

from .ypacket import YPacket, InvalidPacket
from .debug import Debugger
from .callbacks import *
from .const import *
from .im import *
from .utils import *
from .webcam import WebcamConnection
#import const, im, utils

HOSTS = [
    'scs.msg.yahoo.com',
    'scsa.msg.yahoo.com',
    'scsc.msg.yahoo.com',
    'scsd.msg.yahoo.com',
    'scsf.msg.yahoo.com']
FT_HOSTS = [
    '66.196.114.184'
]
PORT = 5050
CLIENT_BUILD_ID = '33554367'
CLIENT_VERSION = '11.5.0.192'
KEEP_ALIVE_TIMEOUT = 30

# init the debugger
debug = Debugger()


class EmussaException(Exception):
    def __init__(self, message, value=EMUSSA_ERROR_UNDEFINED):
        debug.error(message)
        self.message = message
        self.value = value

    def __str__(self):
        return self.message


class EmussaSession:
    def __init__(self):
        self.cbs = {}
        self.debug = debug
        self.queue = queue.Queue()
        self.debug.info('Hi, libemussa here!')
        self._reset()

    def _reset(self):
        self.username = ''
        self.password = ''
        self.session_id = b'\x00\x00\x00\x00'
        self.is_invisible = False
        self.is_connected = False
        self.last_keepalive = 0
        self.y_cookie = self.t_cookie = ''
        self.buddylist = OrderedDict()
        self.addressbook = []
        self.host = choice(HOSTS)
        self.port = 5050
        self.ft_host = choice(FT_HOSTS)
        # FIXME: find a better way to identify webcam requests
        self.webcam_request = None

    def _callback(self, callback_id, *args):
        if callback_id in self.cbs:
            for func in self.cbs[callback_id]:
                func(self, *args)

    def _get_status_type(self):
        if self.is_invisible:
            return YAHOO_STATUS_INVISIBLE
        else:
            return YAHOO_STATUS_AVAILABLE

    def _connect(self, server, port):
        try:
            debug.info('Connecting to {0}:{1}'.format(server, port))
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((server, port))
            debug.info('Connection successful')
            self.is_connected = True
            threading.Thread(target=self._listener).start()
        except Exception as e:
            self.is_connected = False
            debug.error('Connection failed')
            self._callback(EMUSSA_CALLBACK_CONNECTIONFAILED, e)
            self._disconnect()

    def _disconnect(self):
        if self.is_connected:
            self.is_connected = False
            self.s.shutdown(socket.SHUT_WR)
            self.queue.put(None)  # put this in queue to force stopping the sender thread
        self._reset()
        self._callback(EMUSSA_CALLBACK_DISCONNECTED)

    def _listener(self):
        if not self.is_connected:
            e = EmussaException("Cannot listen to an uninitialized socket", EMUSSA_ERROR_NOSOCKET)
            self._callback(EMUSSA_CALLBACK_CONNECTIONFAILED, e)
            self._disconnect()
            raise e

        debug.info('Starting the socket listener')
        while self.is_connected:
            header = body = b''
            try:
                header = self.s.recv(20)
                y = YPacket()
                y.setHeader(header)
                while len(body) < y.length:
                    body += self.s.recv(y.length - len(body))
                y.setData(body)
                self._process_packet(y)
            except InvalidPacket:
                debug.warning('Invalid packet received, skipping')
            # except:
            #     debug.error('Unexpected error while reading data packed')
        debug.info('Listener thread ended.')
        self.is_connected = False

    def _sender(self):
        if not self.is_connected:
            EmussaException("Cannot write to an uninitialized socket", EMUSSA_ERROR_NOSOCKET)

        debug.info('Starting the socket writer')
        while self.is_connected:
            ypack = self.queue.get(True)
            if not ypack:
                continue
            ypack.sid = self.session_id
            debug.info('Sending packet of type {0}'.format(hex(ypack.service)))
            self.s.sendall(ypack.encode())
            debug.info('Sent {0} bytes'.format(len(ypack.encode())))
            self.queue.task_done()
        debug.info('Sender thread ended.')

    def _send(self, y):
        if not self.is_connected:
            self._connect(self.host, self.port)
            threading.Thread(target=self._sender).start()
        self.queue.put(y)

    def _keepalive(self):
        self.last_keepalive = time.time()
        while self.is_connected:
            time.sleep(1)
            if self.last_keepalive + KEEP_ALIVE_TIMEOUT < time.time() and self.is_connected:
                y = YPacket()
                y.service = YAHOO_SERVICE_KEEPALIVE
                y.status = self._get_status_type()
                y.data['0'] = self.username
                self._send(y)
                self.last_keepalive = time.time()

    def _process_packet(self, y):
        debug.info('Received packet of type {0}, size {1}'.format(hex(y.service), y.length))
        if y.sid != "\x00\x00\x00\x00":
            debug.info('Setting session id')
            self.session_id = y.sid

        if y.service == YAHOO_SERVICE_AUTH:
            challenge = y.data['94']
            self._auth_response(challenge)

        elif y.service == YAHOO_SERVICE_LIST:
            self._received_own_contact(y.data)

        elif y.service == YAHOO_SERVICE_LIST_15:
            if y.status == YAHOO_STATUS_AVAILABLE:
                # List complete
                self._received_buddylist(y.data, True)
            else:
                # This is just a part of the list
                self._received_buddylist(y.data, False)

        elif y.service == YAHOO_SERVICE_STATUS_15:
            self._buddy_online(y.data)

        elif y.service == YAHOO_SERVICE_LOGOFF:
            self._buddy_offline(y.data)

        elif y.service == YAHOO_SERVICE_NOTIFY:
            if y.data['49'] == 'TYPING':
                self._typing(y.data)
            elif y.data['49'] == 'WEBCAMINVITE':
                self._webcaminvite(y.data)

        elif y.service == YAHOO_SERVICE_MESSAGE:
            offline = y.status == 5
            self._message_received(y.data, offline)

        elif y.service == YAHOO_SERVICE_Y6_STATUS_UPDATE:
            self._buddy_changed_status(y.data)

        elif y.service == YAHOO_SERVICE_AVATAR_UPDATE:
            self._avatar_update_received(y.data)

        elif y.service == YAHOO_SERVICE_PICTURE_CHECKSUM:
            self._process_picture_checksum(y.data)

        elif y.service == YAHOO_SERVICE_SETTINGS:
            self._set_settings(y.data)

        elif y.service == YAHOO_SERVICE_ADD_BUDDY:
            if y.status == YAHOO_RETCODE_OK:
                self._add_request_response(y.data)

        elif y.service == YAHOO_SERVICE_AUTH_REQ_15:
            if y.status == YAHOO_ADD_REQUEST_AUTHORIZED:
                self._add_auth_response_accept(y.data)
            if y.status == YAHOO_ADD_REQUEST_DENIED:
                self._add_auth_response_rejected(y.data)
            if y.status == YAHOO_ADD_REQUEST_ASK:
                self._auth_request(y.data)

        elif y.service == YAHOO_SERVICE_REMOVE_BUDDY:
            if y.status == YAHOO_RETCODE_OK:
                self._remove_buddy_response(y.data)
            elif y.status == YAHOO_STATUS_AVAILABLE:
                self._remove_buddy(y.data)

        elif y.service == YAHOO_SERVICE_CHANGE_GROUP:
            if y.status == YAHOO_RETCODE_OK:
                self._move_buddy_response(y.data)
            elif y.status == YAHOO_STATUS_AVAILABLE:
                self._move_buddy(y.data)

        elif y.service == YAHOO_SERVICE_AUDIBLE:
            self._audible_received(y.data)

        elif y.service == YAHOO_SERVICE_FILETRANS_15:
            self._file_transfer_request(y.data)

        elif y.service == YAHOO_SERVICE_FILETRANS_INFO_15:
            self._file_transfer_info(y.data)

        elif y.service == YAHOO_SERVICE_FILETRANS_ACC_15:
            self._file_accepted(y.data)

        elif y.service == YAHOO_SERVICE_WEBCAM:
            self._webcam_info_received(y.data)

        elif y.service == YAHOO_SERVICE_DISCONNECT:
            self._disconnect()

        else:
            debug.warning('Unknown packet of type {0}, skipping'.format(hex(y.service)))

    def _request_auth(self):
        y = YPacket()
        y.service = YAHOO_SERVICE_AUTH
        y.status = self._get_status_type()
        y.data['1'] = self.username
        self._send(y)

    def _auth_response(self, challenge):
        debug.info('Requesting token')
        token_url = YAHOO_TOKEN_URL.format(self.username, self.password, urllib.parse.quote(challenge))
        lines = urllib.request.urlopen(token_url).read().decode().split('\r\n')
        errcode = lines[0]
        if errcode == '0':
            debug.info('Got token')
        elif errcode == '100':
            e = EmussaException("Missing required field (username or password).", EMUSSA_ERROR_MISSING_REQUIRED_FIELD)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1013':
            e = EmussaException("Username contains @yahoo.com or similar but should not; strip this information.", EMUSSA_ERROR_CONTAINS_AT_YAHOO_COM)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1212':
            e = EmussaException("The username or password is incorrect.", EMUSSA_ERROR_INCORRECT_CREDENTIALS)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1213' or errcode == '1236':
            e = EmussaException("The account is locked because of too many login attempts.", EMUSSA_ERROR_ACC_LOCKED)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1214':
            e = EmussaException("Security lock requiring the use of a CAPTCHA.", EMUSSA_ERROR_NEED_CAPTCHA)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1218':
            e = EmussaException("The account has been deactivated by Yahoo.", EMUSSA_ERROR_ACC_DEACTIVATED)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        elif errcode == '1235':
            e = EmussaException("The username does not exist.", EMUSSA_ERROR_ACC_NOT_EXISTS)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        else:
            e = EmussaException("Login error: {0}".format(errcode), EMUSSA_ERROR_UNDEFINED)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e

        token_string = ''
        for line in lines[1:len(lines)]:
                key, value = line.split('=', 1)
                if key == 'ymsgr':
                    token_string = value

        if not len(token_string):
            e = EmussaException("Invalid token received.", EMUSSA_ERROR_INVALID_TOKEN)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e

        debug.info('Requesting cookies')
        login_url = YAHOO_LOGIN_URL.format(token_string)
        lines = urllib.request.urlopen(login_url).read().decode().split('\r\n')
        errcode == lines[0]
        if errcode != '0':
            e = EmussaException("Token rejected by server.", EMUSSA_ERROR_INVALID_TOKEN)
            self._callback(EMUSSA_CALLBACK_SIGNINERROR, e)
            self._disconnect()
            raise e
        debug.info('Got cookies')

        crumb = ''
        for line in lines[1:len(lines)]:
            if not '=' in line:
                continue

            key, value = line.split('=', 1)
            if key == 'crumb':
                crumb = value
            if key == 'Y':
                self.y_cookie = value
            if key == 'T':
                self.t_cookie = value

        hash = yahoo_generate_hash(crumb + challenge)
        y = YPacket()
        y.service = YAHOO_SERVICE_AUTHRESP
        y.status = self._get_status_type()
        y.data['0'] = self.username
        y.data['1'] = self.username
        y.data['277'] = self.y_cookie
        y.data['278'] = self.t_cookie
        y.data['307'] = hash
        y.data['244'] = CLIENT_BUILD_ID
        y.data['2'] = '1'
        y.data['59'] = ''
        y.data['98'] = 'us'
        y.data['135'] = CLIENT_VERSION
        self._send(y)
        self._callback(EMUSSA_CALLBACK_ISCONNECTED)

    def _received_own_contact(self, data):
        debug.info('Received self details')
        pi = PersonalInfo()
        pi.yahoo_id = data['3']
        pi.name = data['216']
        pi.surname = data['254']
        pi.country = data['470']
        self._callback(EMUSSA_CALLBACK_SELFCONTACT, pi)

        debug.info('Starting keepalive thread')
        threading.Thread(target=self._keepalive).start()

    def _received_buddylist(self, data, complete=False):
        mode = ''
        for kv in data.asKeyVals():
            if kv.key == '300':
                mode = kv.value

            if kv.key == '65':
                group = Group()
                group.name = kv.value
                self.buddylist[group] = []
                self._callback(EMUSSA_CALLBACK_GROUP_RECEIVED, group)

            if kv.key == '7':
                buddy = Buddy()
                buddy.yahoo_id = kv.value
                buddy.status = Status()
                buddy.status.code = YAHOO_STATUS_OFFLINE
                if mode == '320':
                    buddy.ignored = True
                self.buddylist[next(reversed(self.buddylist))].append(buddy)
                self._callback(EMUSSA_CALLBACK_BUDDY_RECEIVED, buddy)

            if kv.key == '223':
                if kv.value == '1' and buddy:
                    buddy.pending = True

        if complete:
            self._callback(EMUSSA_CALLBACK_BUDDYLIST_RECEIVED, self.buddylist)

    def _get_addressbook(self):
        url = 'http://address.yahoo.com/yab/us?v=XM&prog=ymsgr&.intl=us&diffs=1&t=' \
              '0&tags=short&rt=0&prog-ver={0}&useutf8=1&legenc=codepage-1252'.format(
              CLIENT_VERSION)
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/4.0 (compatible; MSIE 5.5)')]
        opener.addheaders.append(('Cookie', 'Y={0}; T={1}'.format(self.y_cookie, self.t_cookie)))
        req = opener.open(url)
        xmldata = req.read()
        self.addressbook = utils.contacts_from_xml(xmldata)

        self._callback(EMUSSA_CALLBACK_ADDRESSBOOK_RECEIVED, self.addressbook)

    def _update_contact(self, contact):
        # Build xml data
        xmldata = '<?xml version="1.0" encoding="utf-8"?><ab k="{0}" cc="1">'\
                  '{1}</ab>'.format(self.username, utils.contact_to_xml(contact)).encode()

        url = 'http://address.yahoo.com/yab/us?v=XM&prog=ymsgr' \
              '&.intl=us&sync=1&tags=short&noclear=1&useutf8=1&legenc=codepage-1252'
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/4.0 (compatible; MSIE 5.5)')]
        opener.addheaders.append(('Cookie', 'Y={0}; T={1}'.format(self.y_cookie, self.t_cookie)))
        opener.open(url, xmldata)

    def _buddies_from_data(self, data):
        buddies = []

        buddy = None
        for kv in data.asKeyVals():
            if kv.key == '7':
                buddy = Buddy()
                buddy.yahoo_id = kv.value
                buddy.status = Status()
                buddy.status.code = YAHOO_STATUS_AVAILABLE
                buddies.append(buddy)
            if kv.key == '10':
                if buddy:
                    buddy.status.online = True
            if kv.key == '19':
                if buddy:
                    buddy.status.message = kv.value
            if kv.key == '47':
                if buddy:
                    if kv.value == '0':
                        buddy.status.code = YAHOO_STATUS_AVAILABLE
                    elif kv.value == '1':
                        buddy.status.code = YAHOO_STATUS_BUSY
                    elif kv.value == '2':
                        buddy.status.code = YAHOO_STATUS_BRB
            if kv.key == '137':
                if buddy:
                    buddy.status.idle_time = kv.value

        return buddies

    def _buddy_online(self, data):
        debug.info('Set buddy online')
        updated_buddies = self._buddies_from_data(data)

        for ub in updated_buddies:
            self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, ub)
        self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE_LIST, updated_buddies)

    def _buddy_offline(self, data):
        debug.info('Set buddy offline')
        buddies = self._buddies_from_data(data)
        for buddy in buddies:
            buddy.yahoo_id = data['7']
            buddy.status = Status()
            buddy.status.online = False
            self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, buddy)
        self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE_LIST, buddies)

    def _buddy_changed_status(self, data):
        debug.info('Update buddy status')
        buddies = self._buddies_from_data(data)
        for buddy in buddies:
            self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, buddy)
        self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE_LIST, buddies)

    def _avatar_update_received(self, data):
        debug.info('Update buddy display image')
        display_image = DisplayImage()
        if '4' in data:
            display_image.yahoo_id = data['4']
        # if '5' in data:
        #     display_image.yahoo_id = self.username
        if '213' in data:
            display_image.type = int(data['213'])

        if display_image.yahoo_id:
            time.sleep(1)
            try:
                display_image.image_data = utils.download_display_image(
                    display_image.yahoo_id, self.t_cookie, self.y_cookie
                )
            except urllib.error.HTTPError:
                debug.error('HTTP error while downloading avatar for {0}'.format(display_image.yahoo_id))
            except:
                debug.error('Unknown error while downloading avatar for {0}'.format(display_image.yahoo_id))
            self._callback(EMUSSA_CALLBACK_AVATAR_UPDATED, display_image)

    def _process_picture_checksum(self, data):
        checksum = ''
        if '192' in data:
            checksum = int(data['192'])
        if '4' in data:
            yahoo_id = data['4']

    def _typing(self, data):
        typing = TypingNotify()
        if '4' in data:
            typing.sender = data['4']
        typing.receiver = data['5']
        typing.status = int(data['13'])
        if typing.status:
            debug.info('Typing: {0}'.format(typing.sender))
        else:
            debug.info('End typing: {0}'.format(typing.sender))
        self._callback(EMUSSA_CALLBACK_TYPING_NOTIFY, typing)

    def _webcaminvite(self, data):
        print(data)
        wnotify = WebcamNotify()
        if '4' in data:
            wnotify.sender = data['4']
        wnotify.receiver = data['5']
        wnotify.ind = data['14']
        if '15' in data:
            wnotify.status = int(data['15'])
        if wnotify.ind.startswith(' '):
            self._callback(EMUSSA_CALLBACK_WEBCAM_INVITE, wnotify)

    def _message_received(self, data, offline=False):
        if offline:
            debug.info('Got offline messages')
        else:
            debug.info('IM received')
        messages = []

        msg = None
        for kv in data.asKeyVals():
            if kv.key == '4':
                msg = PersonalMessage()
                msg.offline = offline
                msg.sender = kv.value

            if kv.key == '1' and not msg:
                # this is a message we sent from another device
                msg = PersonalMessage()

            if kv.key == '5' and msg:
                msg.receiver = kv.value

            if kv.key == '15' and msg:
                msg.timestamp = kv.value

            if kv.key == '14' and msg:
                msg.message = kv.value

            if kv.key == '429' and msg:
                msg.id = kv.value

            if kv.key == '455' and msg:
                # end of message
                messages.append(msg)
                msg = None

        #messages.reverse()
        for message in messages:
            self._callback(EMUSSA_CALLBACK_MESSAGE_IN, message)
            if message.id:
                self._send_acknowledgement(message)

    def _sign_out(self):
        y = YPacket()
        y.service = YAHOO_SERVICE_LOGOFF
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['505'] = '0'
        self._send(y)
        self._callback(EMUSSA_CALLBACK_SIGNED_OUT)
        self._disconnect()

    def _send_message(self, msg):
        y = YPacket()
        y.service = YAHOO_SERVICE_MESSAGE
        y.status = self._get_status_type()
        y.data['1'] = self.username
        y.data['5'] = msg.receiver
        y.data['14'] = msg.message
        self._send(y)
        self._callback(EMUSSA_CALLBACK_MESSAGE_SENT)

    def _send_acknowledgement(self, msg):
        # Send acknowledgement after receiving a message or
        # we will received again later, after ~7 seconds
        y = YPacket()
        y.service = YAHOO_SERVICE_MESSAGE_ACK
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = self.username
        y.data['5'] = msg.sender
        y.data['302'] = '430'
        y.data['430'] = msg.id
        y.data['303'] = '430'
        y.data['450'] = '0'

        self._send(y)
        # this is just an acknowledgement, no callback here

    def _set_status(self, status):
        is_not_available = '1'
        if status.code == YAHOO_STATUS_AVAILABLE:
            is_not_available = '0'
        y = YPacket()
        y.service = YAHOO_SERVICE_Y6_STATUS_UPDATE
        y.status = self._get_status_type()
        y.data['10'] = str(status.code)
        y.data['19'] = status.message
        y.data['47'] = is_not_available

        if status.message:
            # fix status type if the client did it wrong
            y.data.replace_key('10', 0, str(YAHOO_STATUS_CUSTOM))
            y.data['97'] = '1'  # this means UTF8, I guess
        self._send(y)
        self._callback(EMUSSA_CALLBACK_STATUS_CHANGED, status)

    def _toggle_visible(self, invisible = False):
        y = YPacket()
        y.service = YAHOO_SERVICE_Y6_VISIBLE_TOGGLE
        y.status = self._get_status_type()
        if invisible:
            y.data['13'] = '2'
        else:
            y.data['13'] = '1'
        self._send(y)

    def _send_typing(self, tn):
        y = YPacket()
        y.service = YAHOO_SERVICE_NOTIFY
        y.status = YAHOO_STATUS_NOTIFY
        y.data['49'] = 'TYPING'
        y.data['1'] = self.username
        y.data['5'] = tn.receiver
        y.data['241'] = '0'
        y.data['13'] = tn.status
        self._send(y)

    def _send_add_request(self, add):
        y = YPacket()
        y.service = YAHOO_SERVICE_ADD_BUDDY
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['65'] = add.group
        y.data['97'] = '1'
        y.data['14'] = add.message
        y.data['302'] = '319'
        y.data['300'] = '319'
        y.data['7'] = add.yahoo_id
        y.data['301'] = '319'
        y.data['303'] = '319'
        y.data['216'] = add.fname
        y.data['254'] = add.lname
        y.data['1'] = add.sender
        self._send(y)

    def _send_remove_buddy(self, rem):
        y = YPacket()
        y.service = YAHOO_SERVICE_REMOVE_BUDDY
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = rem.sender
        y.data['7'] = rem.yahoo_id
        y.data['241'] = '0'
        y.data['65'] = rem.group
        self._send(y)

    def _send_move_buddy(self, mv):
        y = YPacket()
        y.service = YAHOO_SERVICE_CHANGE_GROUP
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = mv.sender
        y.data['302'] = '240'
        y.data['300'] = '240'
        y.data['7'] = mv.yahoo_id
        y.data['224'] = mv.from_group
        y.data['264'] = mv.to_group
        y.data['301'] = '240'
        y.data['303'] = '240'
        self._send(y)

    def _add_request_response(self, data):
        re = AddRequestResponse()
        re.sender = data['1']
        re.yahoo_id = data['7']
        re.group = data['65']
        if data['66'] == '0':
            re.success = True
        self._callback(EMUSSA_CALLBACK_AUTH_RESPONSE, re)

    def _add_auth_response_accept(self, data):
        auth = BuddyAuthorization()
        auth.sender = data['4']
        auth.receiver = data['5']
        auth.response = YAHOO_ADD_REQUEST_AUTHORIZED
        if '14' in data:
            auth.message = data['14']
        self._callback(EMUSSA_CALLBACK_AUTH_ACCEPTED, auth)

    def _add_auth_response_rejected(self, data):
        auth = BuddyAuthorization()
        auth.sender = data['4']
        auth.receiver = data['5']
        auth.response = YAHOO_ADD_REQUEST_DENIED
        if '14' in data:
            auth.message = data['14']
        self._callback(EMUSSA_CALLBACK_AUTH_REJECTED, auth)

    def _auth_request(self, data):
        debug.info('Auth response received')
        auth = BuddyAuthorization()
        auth.sender = data['4']
        auth.receiver = data['5']
        auth.fname = data['216']
        auth.lname = data['254']
        auth.response = YAHOO_ADD_REQUEST_ASK
        if '14' in data:
            auth.message = data['14']
        self._callback(EMUSSA_CALLBACK_AUTH_REQUEST, auth)

    def _reject_auth_request(self, auth):
        y = YPacket()
        y.service = YAHOO_SERVICE_AUTH_REQ_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = auth.sender
        y.data['5'] = auth.receiver
        y.data['13'] = '2'
        y.data['14'] = auth.message
        self._send(y)

    def _accept_auth_request(self, auth):
        y = YPacket()
        y.service = YAHOO_SERVICE_AUTH_REQ_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = auth.sender
        y.data['5'] = auth.receiver
        y.data['13'] = '1'
        self._send(y)

    def _remove_buddy_response(self, data):
        rem = RemoveBuddy()
        rem.sender = data['1']
        rem.yahoo_id = data['7']
        rem.group = data['65']
        self._callback(EMUSSA_CALLBACK_REMRESPONSE, rem)

    def _remove_buddy(self, data):
        rem = RemoveBuddy()
        rem.sender = data['1']
        rem.yahoo_id = data['7']
        rem.group = data['65']
        self._callback(EMUSSA_CALLBACK_REMOVEBUDDY, rem)

    def _move_buddy_response(self, data):
        mv = MoveBuddy()
        mv.sender = data['1']
        mv.yahoo_id = data['7']
        mv.from_group = data['224']
        mv.to_group = data['264']
        self._callback(EMUSSA_CALLBACK_MOVERESPONSE, mv)

    def _move_buddy(self, data):
        mv = MoveBuddy()
        mv.sender = data['1']
        mv.yahoo_id = data['7']
        mv.from_group = data['224']
        mv.to_group = data['264']
        self._callback(EMUSSA_CALLBACK_MOVEBUDDY, mv)

    def _send_display_image(self, display_image):
        y = YPacket()
        y.service = YAHOO_SERVICE_AVATAR_UPDATE
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['3'] = display_image.yahoo_id
        y.data['213'] = '{0}'.format(display_image.type)
        self._send(y)

    def _audible_received(self, data):
        debug.info('Audible received')
        a = Audible()
        a.sender = data['4']
        a.receiver = data['5']
        a.name = data['230']
        a.url = '{0}/{1}/{2}.swf'.format(a.base_url, a.name.split('.')[1], a.name)
        a.message = data['231']
        self._callback(EMUSSA_CALLBACK_AUDIBLE_RECEIVED, a)

    def _file_transfer_request(self, data):
        debug.info('File transfer request')
        files = []
        sender = ''
        receiver = ''
        transfer_id = ''
        thumbnail = ''
        transfer_mode = 0

        for kv in data.asKeyVals():
            if kv.key == '4':
                sender = kv.value
            if kv.key == '5':
                receiver = kv.value
            if kv.key == '265':
                transfer_id = kv.value
            if kv.key == '222':
                transfer_mode = int(kv.value)
            if kv.key == '267':
                thumbnail = kv.value
            if kv.key == '27':
                f = File()
                f.filename = kv.value
                files.append(f)
            if kv.key == '28':
                f.filesize = int(kv.value)

        ft = FileTransfer()
        ft.sender = sender
        ft.receiver = receiver
        ft.transfer_id = transfer_id
        ft.thumbnail = thumbnail
        ft.files = files

        if transfer_mode == YAHOO_FILE_TRANSFER_SEND:
            self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_REQUEST, ft)
        elif transfer_mode == YAHOO_FILE_TRANSFER_CANCEL:
            self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_CANCELLED, ft)
        elif transfer_mode == YAHOO_FILE_TRANSFER_ACCEPT:
            self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_ACCEPT, ft)
        elif transfer_mode == YAHOO_FILE_TRANSFER_REJECT:
            self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_REJECT, ft)

    def _file_transfer_info(self, data):
        debug.info('Got file transfer information')
        ftinfo = FileTransferInfo()
        ftinfo.sender = data['4']
        ftinfo.receiver = data['5']
        ftinfo.filename = data['27']
        ftinfo.transfer_type = int(data['249'])
        ftinfo.host = data['250']
        ftinfo.relay_id = data['251']
        ftinfo.transfer_id = data['265']
        self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_INFO, ftinfo)

    def _file_accepted(self, data):
        ftinfo = FileTransferInfo()
        ftinfo.sender = data['4']
        ftinfo.receiver = data['5']
        # ftinfo.filename = data['27']
        # ftinfo.transfer_type = int(data['249'])
        # ftinfo.host = data['250']
        ftinfo.transfer_id = data['265']
        if '251' in data:
            ftinfo.relay_id = data['251']
        self._callback(EMUSSA_CALLBACK_FILE_TRANSFER_UPLOAD, ftinfo)

    def _webcam_info_received(self, data):
        debug.info('Received webcam info')
        w = WebcamRequest()
        w.sender = self.webcam_request.receiver
        w.receiver = data['5']
        w.key = data['61']
        w.server = data['102']
        wconn = WebcamConnection(self, w)
        wconn.connect()
        self.webcam_request = None

    def _accept_file_transfer(self, ft):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ft.sender
        y.data['5'] = ft.receiver
        y.data['265'] = ft.transfer_id
        y.data['222'] = str(YAHOO_FILE_TRANSFER_ACCEPT)
        self._send(y)

    def _accept_file(self, ftinfo):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_ACC_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ftinfo.receiver
        y.data['5'] = ftinfo.sender
        y.data['265'] = ftinfo.transfer_id
        y.data['27'] = ftinfo.filename
        y.data['249'] = str(ftinfo.transfer_type)
        y.data['250'] = ftinfo.host
        y.data['251'] = ftinfo.relay_id
        self._send(y)

    def _accept_next_file(self, file_transfer):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_ACC_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = file_transfer.sender
        y.data['5'] = file_transfer.receiver
        y.data['265'] = file_transfer.transfer_id
        y.data['271'] = '1'
        self._send(y)

    def _decline_file_transfer(self, ft):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ft.sender
        y.data['5'] = ft.receiver
        y.data['265'] = ft.transfer_id
        y.data['222'] = str(YAHOO_FILE_TRANSFER_REJECT)
        self._send(y)

    def _cancel_file_transfer(self, ft):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ft.sender
        y.data['5'] = ft.receiver
        y.data['265'] = ft.transfer_id
        y.data['222'] = str(YAHOO_FILE_TRANSFER_CANCEL)
        self._send(y)

    def _send_file_request(self, ft):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ft.sender
        y.data['5'] = ft.receiver
        y.data['265'] = ft.transfer_id
        y.data['222'] = str(YAHOO_FILE_TRANSFER_SEND)
        y.data['266'] = str(len(ft.files))
        if ft.thumbnail:
            y.data['267'] = ft.thumbnail
        y.data['302'] = '268'
        for f in ft.files:
            y.data['300'] = '268'
            y.data['27'] = f.filename
            y.data['28'] = str(f.filesize)
            y.data['301'] = '268'
        y.data['303'] = '268'
        self._send(y)

    def _send_file_info(self, ftinfo):
        y = YPacket()
        y.service = YAHOO_SERVICE_FILETRANS_INFO_15
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = ftinfo.sender
        y.data['5'] = ftinfo.receiver
        y.data['265'] = ftinfo.transfer_id
        y.data['27'] = ftinfo.filename
        y.data['249'] = ftinfo.transfer_type
        y.data['250'] = ftinfo.host
        self._send(y)

    def _set_settings(self, data):
        raw_data = data['211']
        yahoo_parse_settings(raw_data)

    def _send_webcam_request(self, webcam):
        y = YPacket()
        y.service = YAHOO_SERVICE_WEBCAM
        y.status = YAHOO_STATUS_AVAILABLE
        y.data['1'] = webcam.sender
        y.data['5'] = webcam.receiver
        self._send(y)

    def _deny_webcam_request(self, webcam):
        y = YPacket()
        y.service = YAHOO_SERVICE_NOTIFY
        y.status = YAHOO_STATUS_NOTIFY
        y.data['1'] = webcam.sender
        y.data['5'] = webcam.receiver
        y.data['49'] = 'WEBCAMINVITE'
        y.data['14'] = '-1'
        y.data['13'] = '0'
        self._send(y)

    def _accept_webcam_request(self, webcam):
        y = YPacket()
        y.service = YAHOO_SERVICE_NOTIFY
        y.status = YAHOO_STATUS_NOTIFY
        y.data['1'] = webcam.sender
        y.data['5'] = webcam.receiver
        y.data['49'] = 'WEBCAMINVITE'
        y.data['14'] = '1'
        y.data['13'] = '0'
        self._send(y)

    # "public" methods
    def register_callback(self, callback_id, function):
        if callback_id in self.cbs:
            self.cbs[callback_id].append(function)
        else:
            self.cbs[callback_id] = [function]

    def unregister_callback(self, callback_id, function):
        if callback_id in self.cbs:
            if function in self.cbs[callback_id]:
                self.cbs[callback_id].pop(self.cbs[callback_id].index(function))

    def disconnect(self):
        self._disconnect()

    def signin(self, username, password):
        debug.info('Starting authentication')
        self.username = username
        self.password = password
        self._callback(EMUSSA_CALLBACK_ISCONNECTING)
        self._request_auth()

    def signout(self):
        debug.info('Signing out')
        self._sign_out()

    def send_message(self, to, message):
        debug.info('Sending IM to {0}'.format(to))
        msg = PersonalMessage()
        msg.sender = self.username,
        msg.receiver = to
        msg.timestamp = 0
        msg.message = message
        self._send_message(msg)

    def set_status(self, status_id, message):
        debug.info('Setting status to {0}, message: \'{1}\''.format(status_id, message))
        status = Status()
        status.code = status_id
        status.message = message
        status.idle = 0
        self._set_status(status)

    def toggle_visibility(self, invisible):
        if invisible:
            debug.info('Switch visibility to invisible')
            self._toggle_visible(True)
        else:
            debug.info('Switch visibility to visible')
            self._toggle_visible(False)

    def send_typing(self, to, typing):
        debug.info('Sending TYPING ({0}) to {1}'.format(typing, to))
        tn = TypingNotify()
        tn.sender = self.username
        tn.receiver = to
        if typing:
            tn.status = '1'
        else:
            tn.status = '0'
        self._send_typing(tn)

    def get_addressbook(self):
        debug.info('Send addressbook request')
        threading.Thread(target=self._get_addressbook).start()

    def get_display_image(self, yahoo_id):
        debug.info('Downloading display image for {0}'.format(yahoo_id))
        def download_display_image():
            display_image = DisplayImage()
            display_image.yahoo_id = yahoo_id
            display_image.type = DisplayImage.AVATAR_TYPE_ICON
            try:
                display_image.image_data = utils.download_display_image(yahoo_id, self.t_cookie, self.y_cookie)
            except urllib.error.HTTPError:
                debug.error('HTTP error while downloading avatar for {0}'.format(display_image.yahoo_id))
            except:
                debug.error('Unknown error while downloading avatar for {0}'.format(display_image.yahoo_id))
            self._callback(EMUSSA_CALLBACK_AVATAR_UPDATED, display_image)
        threading.Thread(target=download_display_image, args=()).start()

    def upload_display_image(self, image_data):
        debug.info('Setting display image...')
        def upload_display_image():
            utils.upload_display_image(self.username, image_data, self.t_cookie, self.y_cookie)
            self._callback(EMUSSA_CALLBACK_AVATAR_UPLOADED)

        display_image = DisplayImage()
        display_image.yahoo_id = self.username
        display_image.type = DisplayImage.AVATAR_TYPE_ICON
        self._send_display_image(display_image)
        threading.Thread(target=upload_display_image, args=()).start()

    def delete_display_image(self):
        display_image = DisplayImage()
        display_image.yahoo_id = self.username
        display_image.type = DisplayImage.AVATAR_TYPE_NONE
        self._send_display_image(display_image)

    def add_buddy(self, yahoo_id, group, message, fname, lname, service=1):
        debug.info('Adding {0} to {1}'.format(yahoo_id, group))
        add = AddRequest()
        add.sender = self.username
        add.yahoo_id = yahoo_id
        add.group = group
        add.message = message
        add.fname = fname
        add.lname = lname
        add.service = service
        self._send_add_request(add)

    def remove_buddy(self, yahoo_id, group):
        debug.info('Removing {0} from {1}'.format(yahoo_id, group))
        rem = RemoveBuddy()
        rem.sender = self.username
        rem.yahoo_id = yahoo_id
        rem.group = group
        self._send_remove_buddy(rem)

    def move_buddy(self, yahoo_id, from_group, to_group):
        debug.info('Moving {0} from {1} to {2}'.format(yahoo_id, from_group, to_group))
        mv = MoveBuddy()
        mv.sender = self.username
        mv.yahoo_id = yahoo_id
        mv.from_group = from_group
        mv.to_group = to_group
        self._send_move_buddy(mv)

    def reject_auth_request(self, yahoo_id, message=''):
        debug.info('Rejecting add request from {0}'.format(yahoo_id))
        auth = BuddyAuthorization()
        auth.sender = self.username
        auth.receiver = yahoo_id
        auth.response = 2
        auth.message = message
        self._reject_auth_request(auth)

    def accept_auth_request(self, yahoo_id):
        debug.info('Accepting add request from {0}'.format(yahoo_id))
        auth = BuddyAuthorization()
        auth.sender = self.username
        auth.receiver = yahoo_id
        auth.response = 1
        self._accept_auth_request(auth)

    def decline_transfer(self, yahoo_id, transfer_id):
        ft = FileTransfer()
        ft.sender = self.username
        ft.receiver = yahoo_id
        ft.transfer_id = transfer_id
        self._decline_file_transfer(ft)

    def cancel_transfer(self, yahoo_id, transfer_id):
        ft = FileTransfer()
        ft.sender = self.username
        ft.receiver = yahoo_id
        ft.transfer_id = transfer_id
        self._cancel_file_transfer(ft)

    def accept_transfer(self, yahoo_id, transfer_id):
        ft = FileTransfer()
        ft.sender = self.username
        ft.receiver = yahoo_id
        ft.transfer_id = transfer_id
        self._accept_file_transfer(ft)

    def accept_transfer_next_file(self, yahoo_id, transfer_id):
        ft = FileTransfer()
        ft.sender = self.username
        ft.receiver = yahoo_id
        ft.transfer_id = transfer_id
        self._accept_next_file(ft)

    def accept_file(self, sender, receiver, filename,
        transfer_id, transfer_type, host, relay_id):
        """
        accept a file after receiving its transfer info
        not to be confused with accept_transfer, which accepts a transfer req.
        """
        ftinfo = FileTransferInfo()
        ftinfo.sender = sender
        ftinfo.receiver = receiver
        ftinfo.filename = filename
        ftinfo.transfer_id = transfer_id
        ftinfo.transfer_type = transfer_type
        ftinfo.host = host
        ftinfo.relay_id = relay_id
        self._accept_file(ftinfo)

    def send_files(self, yahoo_id, transfer_id, files, thumbnail=None):
        ft = FileTransfer()
        ft.sender = self.username
        ft.receiver = yahoo_id
        ft.transfer_id = transfer_id
        ft.thumbnail = thumbnail or ''
        ft.files = []
        for path in files:
            if not os.path.exists(path):
                debug.error('File not found: {0}'.format(path))
                return
            if not os.path.isfile(path):
                debug.error('Invalid file: {0}'.format(path))
                return
            f = File()
            f.filename = os.path.basename(path)
            f.filesize = os.path.getsize(path)
            ft.files.append(f)
        self._send_file_request(ft)

    def send_file_info(self, yahoo_id, transfer_id, filename):
        ftinfo = FileTransferInfo()
        ftinfo.sender = self.username
        ftinfo.receiver = yahoo_id
        ftinfo.filename = filename
        ftinfo.transfer_type = '3'
        ftinfo.host = self.ft_host
        ftinfo.transfer_id = transfer_id
        self._send_file_info(ftinfo)

    def update_contact(self, contact):
        threading.Thread(target=self._update_contact, args=(contact,)).start()

    def send_webcam_request(self, yahoo_id):
        webcam = WebcamRequest()
        webcam.sender = self.username
        webcam.receiver = yahoo_id
        self.webcam_request = webcam
        self._send_webcam_request(webcam)

    def deny_webcam_request(self, yahoo_id):
        webcam = WebcamRequest()
        webcam.sender = self.username
        webcam.receiver = yahoo_id
        self.webcam_request = None
        self._deny_webcam_request(webcam)

    def accept_webcam_request(self, yahoo_id):
        webcam = WebcamRequest()
        webcam.sender = self.username
        webcam.receiver = yahoo_id
        self.webcam_request = None
        self._accept_webcam_request(webcam)
