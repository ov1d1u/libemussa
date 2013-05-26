import socket, urllib.parse, urllib.request, threading, time
import queue

from .ypacket import YPacket, InvalidPacket
from .debug import Debugger
from .callbacks import *
from .const import *
from .im import *
from .utils import *
#import const, im, utils

HOST = 'scsa.msg.yahoo.com'
PORT = 5050
CLIENT_BUILD_ID = '33554367'
CLIENT_VERSION = '11.5.0.192'
KEEP_ALIVE_TIMEOUT = 30

# init the debugger
debug = Debugger()
queue = queue.Queue()

class EmussaException(Exception):
    def __init__(self, message, value = EMUSSA_ERROR_UNDEFINED):
        debug.error(message)
        self.message = message
        self.value = value

    def __str__(self):
        return self.message

class EmussaSession:
    def __init__(self):
        self.username = ''
        self.password = ''
        self.cbs = {}
        self.session_id = b'\x00\x00\x00\x00'
        self.is_invisible = False
        self.is_connected = False
        self.last_keepalive = 0
        self.y_cookie = self.t_cookie = ''
        self.debug = debug
        self.debug.info('Hi, libemussa here!')

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
            queue.put(None) # put this in queue to force stopping the sender thread
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
            #except:
            #    debug.warning('Error while reading data packet')
        debug.info('Listener thread ended.')
        self.is_connected = False

    def _sender(self):
        if not self.is_connected:
            EmussaException("Cannot write to an uninitialized socket", EMUSSA_ERROR_NOSOCKET)

        debug.info('Starting the socket writer')
        while self.is_connected:
            ypack = queue.get(True)
            if not ypack:
                continue
            ypack.sid = self.session_id
            debug.info('Sending packet of type {0}'.format(hex(ypack.service)))
            self.s.sendall(ypack.encode())
            debug.info('Sent {0} bytes'.format(len(ypack.encode())))
            queue.task_done()
        debug.info('Sender thread ended.')

    def _send(self, y):
        if not self.is_connected:
            self._connect(HOST, PORT)
            threading.Thread(target=self._sender).start()
        queue.put(y)

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
            self._received_buddylist(y.data)

        elif y.service == YAHOO_SERVICE_STATUS_15:
            self._buddy_online(y.data)

        elif y.service == YAHOO_SERVICE_LOGOFF:
            self._buddy_offline(y.data)

        elif y.service == YAHOO_SERVICE_TYPING:
            self._typing(y.data)

        elif y.service == YAHOO_SERVICE_MESSAGE:
            offline = y.status == 5
            self._message_received(y.data, offline)

        elif y.service == YAHOO_SERVICE_Y6_STATUS_UPDATE:
            self._buddy_changed_status(y.data)

        elif y.service == YAHOO_SERVICE_SETTINGS:
            self._set_settings(y.data)

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

    def _received_buddylist(self, data):
        debug.info('Received buddylist')

        mode = ''
        for key in data:
            if key == '300':
                mode = data[key]

            if key == '65':
                group = Group()
                group.name = data[key]
                self._callback(EMUSSA_CALLBACK_GROUP_RECEIVED, group)

            if key == '7':
                buddy = Buddy()
                buddy.yahoo_id = data[key]
                buddy.status = Status()
                if mode == '320':
                    buddy.ignored = True
                self._callback(EMUSSA_CALLBACK_BUDDY_RECEIVED, buddy)

        data.reset()

    def _buddies_from_data(self, data):
        buddies = []

        buddy = None
        for key in data:
            if key == '7':
                buddy = Buddy()
                buddy.yahoo_id = data[key]
                buddy.status = Status()
                buddies.append(buddy)
            if key == '10':
                if buddy:
                    buddy.status.online = True
            if key == '19':
                if buddy:
                    buddy.status.message = data[key]
            if key == '47':
                if buddy:
                    if data[key] == '0':
                        buddy.status.code = YAHOO_STATUS_AVAILABLE
                    elif data[key] == '1':
                        buddy.status.code = YAHOO_STATUS_BUSY
                    elif data[key] == '2':
                        buddy.status.code = YAHOO_STATUS_BRB
            if key == '137':
                if buddy:
                    buddy.status.idle_time = data[key]
        return buddies

    def _buddy_online(self, data):
        debug.info('Set buddy online')
        updated_buddies = self._buddies_from_data(data)

        for ub in updated_buddies:
            self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, ub)

    def _buddy_offline(self, data):
        debug.info('Set buddy offline')
        buddy = Buddy()
        buddy.yahoo_id = data['7']
        buddy.status = Status()
        buddy.status.online = False
        self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, buddy)

    def _buddy_changed_status(self, data):
        debug.info('Update buddy status')
        buddies = self._buddies_from_data(data)
        if buddies:
            buddy = self._buddies_from_data(data)[0]
            self._callback(EMUSSA_CALLBACK_BUDDY_UPDATE, buddy)

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

    def _message_received(self, data, offline = False):
        if offline:
            debug.info('Got offline messages')
        else:
            debug.info('IM received')
        messages = []

        msg = None
        for key in data:
            if key == '4':
                msg = PersonalMessage()
                msg.offline = offline
                msg.sender = data['4']

            if key == '1' and not msg:
                # this is a message we sent from another device
                msg = PersonalMessage()

            if key == '5' and msg:
                msg.receiver = data['5']

            if key == '15' and msg:
                msg.timestamp = data['15']

            if key == '14' and msg:
                msg.message = data['14']

            if key == '429' and msg:
                msg.id = data['429']

            if key == '455' and msg:
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
        y.service = YAHOO_SERVICE_TYPING
        y.status = YAHOO_STATUS_NOTIFY
        y.data['49'] = 'TYPING'
        y.data['1'] = self.username
        y.data['5'] = tn.receiver
        y.data['241'] = '0'
        y.data['13'] = tn.status
        self._send(y)

    def _set_settings(self, data):
        print ('SETTINGS')
        raw_data = data['211']
        yahoo_parse_settings(raw_data)

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

