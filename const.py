YAHOO_TOKEN_URL = 'https://login.yahoo.com/config/pwtoken_get?src=ymsgr&login={0}&passwd={1}&chal={2}'
YAHOO_LOGIN_URL = 'https://login.yahoo.com/config/pwtoken_login?src=ymsgr&ts=&token={0}'


YAHOO_SERVICE_LOGON             = 0x01
YAHOO_SERVICE_LOGOFF            = 0x02
YAHOO_SERVICE_MESSAGE           = 0x06
YAHOO_SERVICE_PING              = 0x12
YAHOO_SERVICE_SETTINGS          = 0x15
YAHOO_SERVICE_NOTIFY            = 0x4B
YAHOO_SERVICE_HANDSHAKE         = 0x4C
YAHOO_SERVICE_WEBCAM            = 0x50
YAHOO_SERVICE_AUTHRESP          = 0x54
YAHOO_SERVICE_LIST              = 0x55
YAHOO_SERVICE_AUTH              = 0x57
YAHOO_SERVICE_ADD_BUDDY         = 0x83
YAHOO_SERVICE_REMOVE_BUDDY      = 0x84
YAHOO_SERVICE_KEEPALIVE         = 0x8a
YAHOO_SERVICE_STATUS_15         = 0xf0
YAHOO_SERVICE_LIST_15           = 0xf1
YAHOO_SERVICE_Y6_VISIBLE_TOGGLE = 0xc5
YAHOO_SERVICE_Y6_STATUS_UPDATE  = 0xc6
YAHOO_SERVICE_AVATAR_UPDATE		= 0xc7
YAHOO_SERVICE_PICTURE_CHECKSUM  = 0xbd
YAHOO_SERVICE_AUDIBLE           = 0xd0
YAHOO_SERVICE_AUTH_REQ_15       = 0xd6
YAHOO_SERVICE_CHANGE_GROUP      = 0xe7
YAHOO_SERVICE_MESSAGE_ACK       = 0xfb
YAHOO_SERVICE_FILETRANS_15		= 0xdc
YAHOO_SERVICE_FILETRANS_INFO_15 = 0xdd
YAHOO_SERVICE_FILETRANS_ACC_15  = 0xde
YAHOO_SERVICE_DISCONNECT		= 0x07d1

YAHOO_STATUS_AVAILABLE  = 0x00
YAHOO_STATUS_BRB        = 0x01
YAHOO_STATUS_BUSY       = 0x02
YAHOO_STATUS_NOTATHOME  = 0x03
YAHOO_STATUS_NOTATDESK  = 0x04
YAHOO_STATUS_NOTINOFFICE= 0x05
YAHOO_STATUS_ONPHONE    = 0x06
YAHOO_STATUS_ONVACATION = 0x07
YAHOO_STATUS_OUTTOLUNCH = 0x08
YAHOO_STATUS_STEPPEDOUT = 0x09
YAHOO_STATUS_INVISIBLE  = 0x0c
YAHOO_STATUS_CUSTOM     = 0x63
YAHOO_STATUS_OFFLINE    = 0xff
YAHOO_STATUS_NOTIFY     = 0x16

YAHOO_RETCODE_OK                = 0x01
YAHOO_RETCODE_ERR_SRVCON        = 0x02
YAHOO_RETCODE_ERR_UPMISSING     = 0x03
YAHOO_RETCODE_ERR_UHASAT        = 0x04
YAHOO_RETCODE_ERR_LOGIN         = 0x05
YAHOO_RETCODE_ERR_UDEACTIVATED  = 0x06
YAHOO_RETCODE_ERR_UNOTEXIST     = 0x07
YAHOO_RETCODE_ERR_LOCKED        = 0x08

YAHOO_ADD_REQUEST_AUTHORIZED    = 0x01
YAHOO_ADD_REQUEST_DENIED        = 0x02
YAHOO_ADD_REQUEST_ASK           = 0x03

YAHOO_FILE_TRANSFER_SEND		= 0x01
YAHOO_FILE_TRANSFER_CANCEL		= 0x02
YAHOO_FILE_TRANSFER_ACCEPT		= 0x03
YAHOO_FILE_TRANSFER_REJECT		= 0x04

YAHOO_FILE_TRANSFER_TYPE_P2P1	= 0x01
YAHOO_FILE_TRANSFER_TYPE_P2P2	= 0x02
YAHOO_FILE_TRANSFER_TYPE_HTTP	= 0x03

EMUSSA_ERROR_NOERROR                = 0x00
EMUSSA_ERROR_UNDEFINED              = 0x01
EMUSSA_ERROR_NOSOCKET               = 0x02
EMUSSA_ERROR_MISSING_REQUIRED_FIELD = 0x03
EMUSSA_ERROR_CONTAINS_AT_YAHOO_COM  = 0x04
EMUSSA_ERROR_INCORRECT_CREDENTIALS  = 0x05
EMUSSA_ERROR_ACC_LOCKED             = 0x06
EMUSSA_ERROR_NEED_CAPTCHA           = 0x07
EMUSSA_ERROR_ACC_DEACTIVATED        = 0x08
EMUSSA_ERROR_ACC_NOT_EXISTS         = 0x09
EMUSSA_ERROR_INVALID_TOKEN          = 0x0a
