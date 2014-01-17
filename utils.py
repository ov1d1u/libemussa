import base64, os
import xml.etree.ElementTree as ET
import time
import urllib.request
import json
import random
from hashlib import md5
from .im import Contact


class YKeyVal:
    def __init__(self, key='', value=''):
        self.key = key
        self.value = value

    def __setitem__(self, key, value):
        self.key = key
        self.value = value

    def __geitem__(self, key):
        return self.value


class YDict:
    def __init__(self):
        self.keyvals = []
        self.iters = {}

    def __setitem__(self, key, value):
        if not key in self.iters:
            self.iters[key] = 0
        self.keyvals.append([key, value])

    def __getitem__(self, key):
        if type(key) == int:
            if key < len(self.keyvals):
                return self.keyvals[key][0]
            else:
                raise IndexError('Index out of bounds')
        elif type(key) == str:
            i = self.get_seek(key)
            for keyval in self._filter_by_key(key)[i:]:
                if keyval[0] == key:
                    self.set_seek(key, i+1)
                    return keyval[1]
            raise KeyError(key)
        else:
            TypeError('Key indices must be str')

    def __delitem__(self, key):
        i = self.get_seek(key)
        for keyval in self._filter_by_key(key)[i:]:
            if keyval[0] == key:
                self.keyvals.remove([keyval[0], keyval[1]])
                self._fix_seek(key)
                return
        raise KeyError(key)

    def __len__(self):
        return len(self.keyvals)

    def __contains__(self, value):
        for keyval in self.keyvals:
            if keyval[0] == value:
                return True
        return False

    def __str__(self):
        text = '{' + os.linesep
        for keyval in self.keyvals:
            text += '  {0} : {1},{2}'.format(keyval[0], keyval[1], os.linesep)
        text += '}'
        return text

    def __repr__(self):
        return str(self)

    def _filter_by_key(self, key):
        l = []
        for keyval in self.keyvals:
            if keyval[0] == key:
                l.append(keyval)
        return l

    def _count_key(self, key):
        i = 0
        for keyval in self.keyvals:
            if keyval[0] == key:
                i += 1
        return i

    def _fix_seek(self, key):
        if self.get_seek(key) >= self._count_key(key):
            self.set_seek(key, self._count_key(key)-1)

    def export_dictionary(self, d):
        d = {}
        for keyval in self.keyvals:
            d[keyval[0]] = keyval[1]
        return d

    def update_keyval(self, key, oldvalue, newvalue):
        for keyval in list(self.keyvals):
            if keyval[0] == key and keyval[1] == oldvalue:
                self.keyvals.remove(keyval)
                self.keyvals.append([key, newvalue])
                return [key, newvalue]
        raise IndexError('No such keyval')

    def remove_keyval(self, key, value):
        i = self.get_seek(key)
        for keyval in self._filter_by_key(key)[i:]:
            if keyval[0] == key and keyval[1] == value:
                self.keyvals.remove(keyval)
                self._fix_seek(key)
                return keyval
        raise IndexError('No such keyval')

    def remove_key(self, key):
        for keyval in list(self.keyvals):
            if keyval[0] == key:
                self.keyvals.remove(keyval)

    def replace_key(self, key, index_of_key, value):
        for keyval in list(self.keyvals[index_of_key:]):
            if keyval[0] == key:
                self.update_keyval(keyval[0], keyval[1], value)
                return
        raise KeyError(key)

    def keys(self):
        keys = []
        for keyval in self.keyvals:
            keys.append(keyval[0])
        return keys

    def keys_list(self, key):
        keys = []
        for keyval in self.keyvals:
            if keyval == key:
                keys.append(keyval[0])
        return keys

    def values(self):
        values = []
        for keyval in self.keyvals:
            values.append(keyval[1])
        return values

    def items(self):
        items = []
        for keyval in self.keyvals:
            items.append((keyval[0], keyval[1]))
        return items

    def has_key(self, key):
        for keyval in self.keyvals:
            if keyval[0] == key:
                return True
        return False

    def get(self, key):
        for keyval in self.keyvals:
            if keyval[0] == key:
                return keyval[1]
        return None

    def clear(self):
        self.keyvals = []
        self.iters = {}

    def setdefault(self, key):
        self.keyvals.append([key, ''])

    def pop(self, key):
        i = self.get_seek(key)
        for keyval in self._filter_by_key(key)[i:]:
            if keyval[0] == key:
                popped = keyval[1]
                self.keyvals.remove(keyval)
                self._fix_seek(key)
                return popped
        raise KeyError(key)

    def copy(self):
        return list(self.keyvals)

    def set_seek(self, key, position):
        keycount = self._count_key(key)
        if position < keycount:
            self.iters[key] = position

    def get_seek(self, key):
        return self.iters[key]

    def reset(self):
        for key in list(self.keys()):
            self.seek_reset(key)

    def seek_reset(self, key):
        self.set_seek(key, 0)

    def get_range(self, key):
        return (0, self._count_key())

    def asKeyVals(self):
        keyvals = []
        for key, value in self.keyvals:
            keyvals.append(YKeyVal(key, value))
        return keyvals


def yahoo_generate_hash(str_data):
    m = md5()
    data = str_data.encode()
    m.update(data)
    hash = m.digest()
    ybase64 = base64.b64encode(hash)
    ybase64 = ybase64.replace(b'+', b'.')
    ybase64 = ybase64.replace(b'/', b'_')
    ybase64 = ybase64.replace(b'=', b'-')

    return ybase64.decode()

def yahoo_generate_transfer_id():
    # adapted from sendfiletask.cpp, Kopete
    new_id = ''

    for i in range(0, 22):
        j = random.randint(0, 61)
        if j < 26:
            new_id += chr(j + ord('a'))
        elif j < 52:
            new_id += chr((j - 26) + ord('A'))
        else:
            new_id += chr((j - 52) + ord('0'))

    new_id += '$$'
    return new_id

def contact_from_xml(xml_data):
    xmlcontact = ET.fromstring(xml_data)
    contact = Contact()
    attrib = xmlcontact.attrib
    if 'id' in attrib:
        contact.id = attrib['id']
    if 'yi' in attrib:
        contact.yahoo_id = attrib['yi']
    if 'nn' in attrib:
        contact.nickname = attrib['nn']
    if 'fn' in attrib:
        contact.fname = attrib['fn']
    if 'mn' in attrib:
        contact.mname = attrib['mn']
    if 'ln' in attrib:
        contact.lname = attrib['ln']
    if 'mo' in attrib:
        contact.mobile = attrib['mo']
    if 'msnid' in attrib:
        contact.msnid = attrib['msnid']
    if 'e0' in attrib:
        contact.email = attrib['e0']
    if 'e1' in attrib:
        contact.email1 = attrib['e1']
    if 'e2' in attrib:
        contact.email2 = attrib['e2']
    if 'c1' in attrib:
        contact.note1 = attrib['c1']
    if 'c2' in attrib:
        contact.note2 = attrib['c2']
    if 'c3' in attrib:
        contact.note3 = attrib['c3']
    if 'c4' in attrib:
        contact.note4 = attrib['c4']
    if 'ha' in attrib:
        contact.home_addr = attrib['ha']
    if 'hc' in attrib:
        contact.home_city = attrib['hc']
    if 'hs' in attrib:
        contact.home_state = attrib['hs']
    if 'hz' in attrib:
        contact.home_zip = attrib['hz']
    if 'hn' in attrib:
        contact.home_country = attrib['hn']
    if 'wa' in attrib:
        contact.work_addr = attrib['wa']
    if 'wc' in attrib:
        contact.work_city = attrib['wc']
    if 'ws' in attrib:
        contact.work_state = attrib['ws']
    if 'wz' in attrib:
        contact.work_zip = attrib['wz']
    if 'wn' in attrib:
        contact.work_country = attrib['wn']
    if 'an' in attrib:
        contact.anniversary = attrib['an']
    if 'bi' in attrib:
        contact.birthday = attrib['bi']
    if 'cm' in attrib:
        contact.note = attrib['cm']
    if 'co' in attrib:
        contact.work_company = attrib['co']
    if 'fa' in attrib:
        contact.fax = attrib['fa']
    if 'hp' in attrib:
        contact.home_phone = attrib['hp']
    if 'imk' in attrib:
        contact.skype = attrib['imk']
    if 'ot' in attrib:
        contact.other_phone = attrib['ot']
    if 'pa' in attrib:
        contact.pager = attrib['pa']
    if 'pu' in attrib:
        contact.website = attrib['pu']
    if 'ti' in attrib:
        contact.job_title = attrib['ti']
    if 'wp' in attrib:
        contact.work_phone = attrib['wp']
    if 'wu' in attrib:
        contact.work_website = attrib['wu']
    return contact


def contact_to_xml(contact):
    if not contact.yahoo_id:    # yahoo_id required when creating a XML contact
        return None
    ct = ET.Element('ct')
    if contact.id:
        ct.attrib['e'] = '1'
        ct.attrib['id'] = contact.id
    else:
        ct.attrib['a'] = '1'
    if contact.yahoo_id:
        ct.attrib['yi'] = contact.yahoo_id
    if contact.fname:
        ct.attrib['fn'] = contact.fname
    if contact.mname:
        ct.attrib['mn'] = contact.mname
    if contact.lname:
        ct.attrib['ln'] = contact.lname
    if contact.nickname:
        ct.attrib['nn'] = contact.nickname
    if contact.email:
        ct.attrib['e0'] = contact.email
    if contact.home_phone:
        ct.attrib['hp'] = contact.home_phone
    if contact.work_phone:
        ct.attrib['wp'] = contact.work_phone
    if contact.mobile:
        ct.attrib['mo'] = contact.mobile
    if contact.job_title:
        ct.attrib['ti'] = contact.job_title
    if contact.fax:
        ct.attrib['fa'] = contact.fax
    if contact.pager:
        ct.attrib['pa'] = contact.pager
    if contact.other_phone:
        ct.attrib['ot'] = contact.other_phone
    if contact.email1:
        ct.attrib['e1'] = contact.email1
    if contact.email2:
        ct.attrib['e2'] = contact.email2
    if contact.website:
        ct.attrib['pu'] = contact.website
    if contact.home_addr:
        ct.attrib['ha'] = contact.home_addr
    if contact.home_city:
        ct.attrib['hc'] = contact.home_city
    if contact.home_state:
        ct.attrib['hs'] = contact.home_state
    if contact.home_zip:
        ct.attrib['hz'] = contact.home_zip
    if contact.home_country:
        ct.attrib['hn'] = contact.home_country
    if contact.work_company:
        ct.attrib['co'] = contact.work_company
    if contact.work_addr:
        ct.attrib['wa'] = contact.work_addr
    if contact.work_city:
        ct.attrib['wc'] = contact.work_city
    if contact.work_state:
        ct.attrib['ws'] = contact.work_state
    if contact.work_zip:
        ct.attrib['wz'] = contact.work_zip
    if contact.work_country:
        ct.attrib['wn'] = contact.work_country
    if contact.work_website:
        ct.attrib['wu'] = contact.work_website
    if contact.birthday:
        ct.attrib['bi'] = contact.birthday
    if contact.anniversary:
        ct.attrib['an'] = contact.anniversary
    if contact.note:
        ct.attrib['cm'] = contact.note
    if contact.note1:
        ct.attrib['c1'] = contact.note1
    if contact.note2:
        ct.attrib['c2'] = contact.note2
    if contact.note3:
        ct.attrib['c3'] = contact.note3
    if contact.note4:
        ct.attrib['c4'] = contact.note4
    if contact.skype:
        ct.attrib['imk'] = contact.skype
    return ET.tostring(ct)


def contacts_from_xml(xml_data):
    contacts = []
    addressbook = ET.fromstring(xml_data)

    for xmlcontact in addressbook:
        contact = contact_from_xml(ET.tostring(xmlcontact))
        contacts.append(contact)
    return contacts

def download_display_image(yahoo_id, t_cookie, y_cookie):
    req = urllib.request.Request(
        'http://rest-img.msg.yahoo.com/v1/displayImage/yahoo/{0}?{1}'.format(yahoo_id, random.randint(1, 9999))
    )
    req.add_header('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US)')
    req.add_header('Cookie', 'Y={0}; T={1}'.format(y_cookie, t_cookie))
    r = urllib.request.urlopen(req)
    return r.read()

def upload_display_image(yahoo_id, image_data, t_cookie, y_cookie):
    # get crumb
    req = urllib.request.Request('http://rest-core.msg.yahoo.com/v1/session?amIOnline=0&rand=/v1/session')
    req.add_header('User-agent', 'net_http_transaction_impl_manager/0.1')
    req.add_header('Cookie', 'Y={0}; T={1}'.format(y_cookie, t_cookie))
    r = urllib.request.urlopen(req)
    data = r.read()
    cd = json.loads(data.decode())
    crumb = cd['crumb']

    # upload the image
    req = urllib.request.Request('http://rest-img.msg.yahoo.com/v1/displayImage/custom/yahoo/{0}?src=orion&c={1}'.format(
            yahoo_id, crumb))
    req.add_header('User-agent', 'net_http_transaction_impl_manager/0.1')
    req.add_header('Content-Type', 'image/png')
    req.add_header('Content-Length', '{0}'.format(len(image_data)))
    req.add_header('Cookie', 'Y={0}; T={1}'.format(y_cookie, t_cookie))
    req.add_data(image_data)
    r = urllib.request.urlopen(req)
    data = r.read()

def random_string(length):
    import random, string
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

def string_to_md5(string):
    import hashlib
    if type(string) == str:
        string = string.encode()
    return hashlib.md5(string).hexdigest()

def string_to_base64(string):
    import base64
    if type(string) == str:
        string = string.encode()
    return base64.b64encode(string).decode()