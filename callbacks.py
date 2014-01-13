"""
Callback identifiers for libemussa

Being asynchronious, libemussa needs to know which methods to call when specific events
occur. This file contains the identifiers used when registering callbacks, along with
a short documentation for each one
"""


EMUSSA_CALLBACK_DISCONNECTED = 0
"""
Prototype:
def callback(EmussaSession emussa):
    ///

Called on disconnection
"""


EMUSSA_CALLBACK_ISCONNECTING = 1
"""
Prototype:
def callback(EmussaSession emussa):
    ///

Called before opening the socket to the YMSG server
"""


EMUSSA_CALLBACK_ISCONNECTED = 2
"""
Prototype:
def callback(EmussaSession emussa):
    ///

Called when the socket connection was successfull.
"""


EMUSSA_CALLBACK_CONNECTIONFAILED = 3
"""
Prototype:
def callback(EmussaSession emussa, Exception e):
    ///

Called when the connection failed. The given parameter is the exception generated on connection failure
"""


EMUSSA_CALLBACK_SIGNINERROR = 4
"""
Prototype:
def callback(EmussaSession emussa, int EMUSSA_ERROR_CODE):
    ///

Called when the signing process failed (because of invalid credentials, locked account, et al).
See const.py for error codes.
"""


EMUSSA_CALLBACK_SELFCONTACT = 5
"""
Prototype:
def callback(EmussaSession emussa, PersonalInfo pi):
    ///

Called when received personal info data; class PersonalInfo is defined in im.py
"""


EMUSSA_CALLBACK_GROUP_RECEIVED = 6
"""
Prototype:
def callback(EmussaSession emussa, Group group):
    ///

Called when a new group is received; class BuddyList is defined in im.py.
"""


EMUSSA_CALLBACK_BUDDY_RECEIVED = 7
"""
Prototype:
def callback(EmussaSession emussa, Buddy buddy):
    ///

Called when a new buddy is received; class Buddy is defined in im.py.
"""


EMUSSA_CALLBACK_BUDDYLIST_RECEIVED = 8
"""
Prototype:
def callback(EmussaSession emussa, OrderedDict buddies)
    ///

Called when the receiving of buddylist is done. The format of buddies is:
buddies['group_name'] = [buddy, buddy, buddy, ...]

Please note that the buddies lists also contains ignored users.
"""


EMUSSA_CALLBACK_BUDDY_UPDATE = 9
"""
Prototype:
def callback(EmussaSession emussa, Buddy b)
    ///

Called when a buddy needs to be updated (e.g. changes its status); class Status is defined in im.py
"""


EMUSSA_CALLBACK_TYPING_NOTIFY = 10
"""
Prototype:
def callback(EmussaSession emussa, TypingNotify tn)
    ///

Called when a typing notification is received; class TypingNotify is defined in im.py
WARNING: If msg.sender is empty it means that the message was sent by ourselves from another device
"""


EMUSSA_CALLBACK_MESSAGE_IN = 11
"""
Prototype:
def callback(EmussaSession emussa, PersonalMessage msg)
    ///

Called when an IM is received; class PersonalMessage is defined in im.py
WARNING: If tn.sender is empty it means that we are typing from another device
"""


EMUSSA_CALLBACK_MESSAGE_SENT = 12
"""
Prototype:
def callback(EmussaSession emussa, PersonalMessage msg)
    ///

Called after a message is sent; class PersonalMessage is defined in im.py
"""


EMUSSA_CALLBACK_STATUS_CHANGED = 13
"""
Prototype:
def callback(EmussaSession emussa, Status status):
    ///

Called when self status (!!) is changed; class Status is defined in im.py
"""


EMUSSA_CALLBACK_SIGNED_OUT = 14
"""
Prototype:
def callback(EmussaSession emussa):
    ///

Called when user is signed out
"""


EMUSSA_CALLBACK_ADDRESSBOOK_RECEIVED = 15
"""
Prototype:
def callback(EmussaSession emussa, list contacts):
    ///

Called when the addressbook was received and parsed. contacts is a list of Contact objects.
"""


EMUSSA_CALLBACK_AUTH_RESPONSE = 16
"""
Prototype:
def callback(EmussaSession emussa, AddRequestResponse re):
    ///

Called when an AddRequestResponse is received; class AddRequestResponse is defined in im.py
"""


EMUSSA_CALLBACK_AUTH_ACCEPTED = 17
"""
Prototype:
def callback(EmussaSession emussa, BuddyAuthorization auth):
    ///

Called when somebody accepted our add request; class BuddyAuthorization is defined
in im.py
"""


EMUSSA_CALLBACK_AUTH_REJECTED = 18
"""
Prototype:
def callback(EmussaSession emussa, BuddyAuthorization auth):
    ///

Called when somebody rejected our add request; class BuddyAuthorization is defined
in im.py
"""


EMUSSA_CALLBACK_AUTH_REQUEST = 19
"""
Prototype:
def callback(EmussaSession emussa, BuddyAuthorization auth):
    ///

Called when somebody ask to allow him adding us in his buddylist; class
BuddyAuthorization is defined in im.py
"""


EMUSSA_CALLBACK_BUDDY_UPDATE_LIST = 20
"""
Prototype:
def callback(EmussaSession emussa, list updated_buddies):
    ///

Called after one or more buddies were updated. Same as EMUSSA_CALLBACK_BUDDY_UPDATE,
but called after receiving the whole updates list, not per buddy. updated_buddies is
a list of buddies with their new properties.
"""


EMUSSA_CALLBACK_REMRESPONSE = 21
"""
Prototype:
def callback(EmussaSession emussa, RemoveBuddy rem):
    ///

Called when a confirmation of buddy deletion comes from Y! servers. RemoveBuddy is defined
in im.py
"""


EMUSSA_CALLBACK_REMOVEBUDDY = 22
"""
Prototype:
def callback(EmussaSession emussa, RemoveBuddy rem):
    ///

Called when a remote buddy deletion occur, usually when a buddy was removed from another
device connected with the same account. RemoveBuddy is defined in im.py
"""


EMUSSA_CALLBACK_MOVERESPONSE = 23
"""
Prototype:
def callback(EmussaSession emussa, MoveBuddy mv):
    ///

Called when a confirmation of buddy move comes from Y! servers. MoveBuddy is defined
in im.py
"""


EMUSSA_CALLBACK_MOVEBUDDY = 24
"""
Prototype:
def callback(EmussaSession emussa, MoveBuddy mv):
    ///

Called when a remote buddy move occur, usually when a buddy was moved from another
device connected with the same account. MoveBuddy is defined in im.py
"""


EMUSSA_CALLBACK_AUDIBLE_RECEIVED = 25
"""
Prototype:
def callback(EmussaSession emussa, Audible a):
    ///

Called when an audible message is received. Audible is defined in im.py
"""


EMUSSA_CALLBACK_AVATAR_UPDATED = 26
"""
Prototype:
def callback(EmussaSession emussa, DisplayImage a)
"""


EMUSSA_CALLBACK_AVATAR_UPLOADED = 27
"""
Prototype:
def callback(EmussaSession emussa)
"""