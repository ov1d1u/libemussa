import socket
import threading
import queue
import struct
from subprocess import Popen, PIPE, STDOUT
from .debug import Debugger
from .callbacks import *
from .utils import *

PORT = 5100
# init the debugger
debug = Debugger()


class WebcamConnection:
    def __init__(self, emussa_session, webcam):
        self.ym = emussa_session
        self.w = webcam
        self.s = None
        self.is_connected = False
        if webcam.sender == emussa_session.username:
            self.direction = 'out'
        else:
            self.direction = 'in'

    def _send(self, data):
        if not self.is_connected:
            debug.error('Webcam: Trying to send data via a closed socket')
        self.queue.put(data)

    def _sender(self):
        while True:
            data = self.queue.get(True)
            if not self.is_connected:
                debug.info('Webcam: disconnected, stop sending...')
                return
            if not data:
                continue
            if type(data) == str:
                data = data.encode()
            self.s.sendall(data)
            self.queue.task_done()

    def _disconnect(self):
        self.s.close()
        self.is_connected = False
        self.queue.put('0')

    def _connect1(self, cb=None):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.w.server, PORT))
        debug.info('Webcam: Connected to webcam server (1)')
        self.is_connected = True
        threading.Thread(target=self._sender).start()

        if cb:
            cb()

    def _connected1(self):
        # first stage connection
        # adapted from webcamtask.cpp (Kopete)
        if self.direction == 'in':
            self._send(b'<RVWCFG>')
            s = 'g={0}\r\n'.format(self.w.sender)
        else:
            self._send(b'<RUPCFG>')
            s = 'f=1\r\n'

        h = b'\x08\x00\x01\x00' + struct.pack('!i', len(s))
        self._send(h)
        self._send(s)

        # throw 2 bytes into the eternal space
        self.s.recv(2)
        # read the signal ID
        sid = self.s.recv(1)
        # another separator, throw it...
        self.s.recv(1)

        if sid == b'\x06':
            self.ym._callback(EMUSSA_CALLBACK_WEBCAM_NOT_AVAILABLE, self.w)
        elif sid == b'\x04' or sid == b'\x07':
            # read the new server address
            new_ip = ''
            while True:
                data = self.s.recv(1)
                if data == b'\x00':
                    break
                new_ip += data.decode()

            debug.info('Webcam: Received server {0}'.format(new_ip))
            self._disconnect()

            # start the second stage
            threading.Thread(target=self._connect2,
                             args=(new_ip, self._connected2)).start()
        else:
            # wot?
            debug.error('Unknown flag {0}'.format(sid))

    def _connect2(self, new_server, cb=None):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((new_server, PORT))
        debug.info('Webcam: Connected to webcam server (2)')
        self.is_connected = True
        threading.Thread(target=self._sender).start()

        if cb:
            cb()

    def _connected2(self):
        if self.direction == 'in':
            debug.info('Webcam: requesting image')
            self._send(b'<REQIMG>')
            s = 'a=2\r\nc=us\r\ne=21\r\nu={0}\r\nt={1}\r\ni=\r\ng={2}\r\n'\
                'o=w-2-5-1\r\np=1'.format(self.ym.username,
                                          self.w.key,
                                          self.w.sender)
            h = b'\x08\x00\x01\x00' + struct.pack('!i', len(s))
        elif self.direction == 'out':
            debug.info('Webcam: sending image')
            self._send(b'<SNDIMG>')
            s = 'a=2\r\nc=us\r\nu={0}\r\nt={1}\r\ni={2}\r\n'\
                'o=w-2-5-1\r\np=2\r\n'\
                'b=CyufWebcam\r\nd=\r\n'.format(self.ym.username,
                                                self.w.key,
                                                socket.gethostbyname(
                                                    socket.gethostname())
                                                )
            h = b'\x0d\x05\x00\x00' + struct.pack('!i', len(s)) +\
                b'\x01\x00\x00\x00\x01'
        self._send(h)
        self._send(s)
        threading.Thread(target=self._readData).start()

    def _readData(self):
        debug.info('Webcam: socket reader started')
        headerLength = 0
        dataLength = 0
        while True:
            if not self.is_connected:
                debug.info('Webcam: disconnected')
                return
            data = b''
            hdata = b''
            while len(hdata) < 1:
                hdata += self.s.recv(1)
            headerLength = ord(struct.unpack('!c', hdata)[0])
            while len(hdata) < headerLength:
                hdata += self.s.recv(1)

            if headerLength >= 8:
                dataLength = yahoo_get32(hdata[4:8])
                while len(data) < dataLength:
                    data += self.s.recv(1)
            if headerLength == 13:
                # print(':'.join("%02x" % b for b in hdata))
                if hdata[8] == ord(b'\x02'):
                    imgdata = data
                    bmpdata = self._convertFrame(data)
                    if bmpdata:
                        self.w.image = bmpdata
                        debug.info('Webcam: received image')
                        cbs = self.ym.cbs[EMUSSA_CALLBACK_WEBCAM_IMAGE_READY]
                        if len(cbs) > 0:
                            self.ym._callback(
                                EMUSSA_CALLBACK_WEBCAM_IMAGE_READY,
                                self.w)
                        else:
                            self._disconnect()
                            debug.error('No callbacks attached, disconnecting')
                            return
                    else:
                        debug.info('Webcam: invalid image')
            if headerLength > 13 or headerLength <= 0:
                continue

    def _convertFrame(self, imagedata):
        p = Popen(
            ['jasper', '--input-format', 'jpc', '--output-format', 'bmp'],
            stdout=PIPE,
            stdin=PIPE,
            stderr=PIPE)
        stdout_data = p.communicate(input=imagedata)[0]
        if len(stdout_data):
            return stdout_data
        else:
            return None

    # "public" methods
    def connect(self):
        self.queue = queue.Queue()

        # connect (1st stage)
        threading.Thread(target=self._connect1,
                         args=(self._connected1, )).start()

    def disconnect(self):
        self._disconnect()
