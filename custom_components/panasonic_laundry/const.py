"""Constants for the Panasonic washer-dryer ("スマホで洗濯") integration.

Everything below was read from the official Android app (com.panasonic.SmartLaundry 2.14.00):
Auth0 client registration (public), API host and paths, and the code tables of the washer's
status properties (ECHONET-Lite-style property ids, e.g. 0080 = operating state).
"""

DOMAIN = "panasonic_laundry"

AUTH0_DOMAIN = "auth.digital.panasonic.com"
AUTH0_CLIENT_ID = "2wSeRcOi0MoAv5ByV1tSUusr5VW3CP4v"
AUTH0_AUDIENCE = f"https://club.panasonic.jp/{AUTH0_CLIENT_ID}/api/v1/"
AUTH0_SCOPE = "openid offline_access smartlaundry.control"
AUTH0_REDIRECT_URI = "auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback"
AUTH0_AUTHORIZE_URL = f"https://{AUTH0_DOMAIN}/authorize"
AUTH0_TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"

API_BASE_URL = "https://app.wad.apws.panasonic.com/laundry/v5"
API_TIMEZONE = "Asia/Tokyo"
API_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S%z"  # X-Timestamp header, e.g. 20261012170000+0900

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_APPLIANCE_ID = "appliance_id"
CONF_NICKNAME = "nickname"
TOKEN_REFRESH_MARGIN_SECONDS = 300
SCAN_INTERVAL_SECONDS = 60

# Property ids of GET /device/status (header X-ApplianceId) used here.
P_POWER = "0080"            # 30 on / 31 off
P_FAULT = "0088"            # 41 fault / 42 none
P_DOOR = "00B0"             # 41 open / 42 closed
P_COURSE = "00D0"           # course code (COURSES)
P_REMAIN_WASH = "00DB"      # HHMM (hex bytes), FFFF = not available
P_REMAIN_DRY = "00DC"
P_REMAIN_ALL = "00ED"       # washing + drying
P_STAGE = "00E2"            # transition state (STAGES)
P_CHILD_LOCK = "00F9"
P_RESERVATION = "0090"      # 41 on / 42 off (on-timer reservation)
P_PROGRESS = "0121"         # driving situation (PROGRESS)

P_REMOTE = "0100"           # 01 remote operation permitted (遠隔 lamp on) / 02 not permitted
P_START = "00B2"            # 41 start / 42 pause / 43 stop
P_RESERVE_FINISH = "0092"   # time until the washer should be finished, two hex bytes HH MM
P_RESERVE_START = "00F2"    # time until the washer starts (computed by the washer), HH MM
P_DETERGENT_MODE = "0132"   # detergent / softener input modes (sent along for washing courses)
P_SOFTENER_MODE = "0133"
P_HISTORY = "012B"          # recent courses: 10 x 4 bytes (course, 3 bytes sub mode), newest first

MAX_RESERVE_MINUTES = 24 * 60

# 00E2 transition state -> (Japanese text, kind); kind: run / pause / done / wait
STAGES = {
    "41": ("運転中 洗い工程", "run"),
    "42": ("運転中 すすぎ工程", "run"),
    "43": ("運転中 脱水工程", "run"),
    "44": ("一時停止中", "pause"),
    "45": ("運転終了 洗濯のみ", "done"),
    "51": ("運転終了 洗乾、ふんわりキープなし", "done"),
    "52": ("運転中 乾燥・送風工程", "run"),
    "53": ("運転終了 ふんわりキープ工程", "done"),
    "54": ("運転終了 洗乾/乾燥のみ、ふんわりキープあり", "done"),
    "61": ("運転前待機中", "wait"),
    "E0": ("運転中 冷却工程", "run"),
    "E1": ("運転中 プレ洗浄工程", "run"),
    "E2": ("運転中 プレ乾燥工程", "run"),
    "E3": ("運転中 ナノイー工程", "run"),
    "EF": ("運転終了 槽クリーン工程", "done"),
}

# 0121 driving situation -> text
PROGRESS = {
    "00": "操作待機中",
    "01": "洗い中",
    "03": "すすぎ中",
    "05": "脱水中",
    "06": "乾燥中",
    "07": "布ほぐし中",
    "08": "ふんわりキープ中",
    "09": "ナノイー運転中",
    "0A": "ナノイー槽クリーン待機中",
    "0B": "ナノイー槽クリーン中",
    "0C": "一時停止中",
    "0D": "乾燥残時間見直し中",
    "0F": "修正すすぎ中",
    "10": "泡消し攪拌中",
    "12": "フィルタ報知中",
    "13": "予約待機中",
    "14": "プレ洗浄中・プレ乾燥中",
    "16": "ジェットほぐし中",
    "18": "ジェット乾燥中",
    "19": "第２送風中",
    "1A": "第２送風中＋フィルタ報知中",
    "1B": "ふんわりキープ中＋フィルタ報知中",
    "1C": "エコナビ点灯中",
    "1E": "自動槽洗浄中",
    "1F": "バスポンプ動作中",
}

# 00D0 course -> text
COURSES = {
    "21": "洗濯・乾燥 おまかせ",
    "22": "洗濯・乾燥 ナイト",
    "23": "洗濯・乾燥 どろんこ（パワフル）",
    "25": "洗濯・乾燥 40℃つけおき",
    "26": "洗濯・乾燥 毛布",
    "29": "洗濯・乾燥 滝すすぎ(VG)/パワフル滝すすぎ(VX)/パワフル滝(洗い・すすぎ)(VX,VG)",
    "2D": "洗濯・乾燥 約60℃おまかせ(VG)/60℃除菌(VX)",
    "32": "洗濯・乾燥 化繊60分",
    "40": "洗濯・乾燥 おまかせ＋プレ洗浄",
    "41": "洗濯・乾燥 個別洗濯",
    "42": "洗濯・乾燥 ダニバスター",
    "44": "洗濯・乾燥 40℃おまかせ",
    "45": "洗濯・乾燥 40℃においスッキリ",
    "47": "洗濯・乾燥 タオル専用",
    "49": "洗濯・乾燥 40℃つけおき(普段着)",
    "4A": "洗濯・乾燥 約40℃毛布",
    "4E": "洗濯・乾燥 省エネ",
    "4F": "洗濯・乾燥 わたし流(VG)/わたし流プラス(VX)/わが家流(VG)/わが家流プラス(VX)",
    "61": "洗濯 おまかせ",
    "62": "洗濯 ナイト",
    "63": "洗濯 どろんこ（パワフル）",
    "65": "洗濯 約40℃つけおき（おしゃれ着）",
    "66": "洗濯 毛布",
    "67": "洗濯 約30℃おしゃれ着",
    "68": "洗濯 おうちクリーニング",
    "69": "洗濯・乾燥 滝すすぎ(VG)/パワフル滝すすぎ(VX)/パワフル滝(洗い・すすぎ)(VX,VG)",
    "6A": "約60℃おまかせ(VG)/60℃除菌(VX)",
    "7F": "洗濯 槽洗浄",
    "80": "洗濯 おまかせ＋プレ洗浄",
    "81": "洗濯 個別洗濯",
    "82": "洗濯 ダニバスター",
    "83": "洗濯 パワフル（約30℃）槽洗浄",
    "84": "洗濯 約40℃おまかせ",
    "85": "洗濯 約40℃においスッキリ",
    "86": "洗濯 約40 ℃おしゃれ着",
    "88": "洗濯 約60℃槽カビクリーン",
    "89": "洗濯 約40℃つけおき(普段着)",
    "8A": "洗濯 約40℃毛布",
    "8F": "洗濯 わたし流(VG)/わたし流プラス(VX)/わが家流(VG)/わが家流プラス(VX)",
    "A1": "乾燥 おまかせ",
    "A2": "乾燥 毛布",
    "A3": "乾燥 ソフト乾燥",
    "BF": "乾燥 槽乾燥",
    "CC": "乾燥 ナノイー/ナノイーＸ",
    "CD": "乾燥 ナイト",
    "CE": "乾燥 省エネ",
    "CF": "乾燥 わたし流(VG)/わたし流プラス(VX)/わが家流(VG)/わが家流(VX)",
}
