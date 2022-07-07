import datetime
import logging
import re
import time
import pynmea2

from serial_conn import SerialConn
from retrying import retry
from common_util import dict_key_by_value

log = logging.getLogger(__name__)

# +CME ERROR: unknown
error_regex = re.compile("ERROR|\+(?P<type>.+) ERROR: (?P<reason>.+)")


class LE910CXException(Exception):
    pass

class NoFixException(LE910CXException):
    pass

class InvalidResponseException(LE910CXException):
    pass

class CommandExecutionException(LE910CXException):
    pass


SMS_FORMAT_MODE_PUD = 0
SMS_FORMAT_MODE_TEXT = 1

SMS_FORMAT_MODES = {
    SMS_FORMAT_MODE_PUD:  "PUD",
    SMS_FORMAT_MODE_TEXT: "TXT"
}

SMS_DELETE_ALL = 1

GNSS_LOCATION_FIX_INVALID_FIX = 0
GNSS_LOCATION_FIX_NO_FIX      = 1
GNSS_LOCATION_FIX_2D_FIX      = 2
GNSS_LOCATION_FIX_3D_FIX      = 3

GNSS_LOCATION_FIX_MAP = {
    GNSS_LOCATION_FIX_INVALID_FIX: "invalid_fix",
    GNSS_LOCATION_FIX_NO_FIX:      "no_fix",
    GNSS_LOCATION_FIX_2D_FIX:      "2D",
    GNSS_LOCATION_FIX_3D_FIX:      "3D",
}

NMEA_MODE_DISABLED   = 0
NMEA_MODE_FIRST_FMT  = 1
NMEA_MODE_SECOND_FMT = 2
NMEA_MODE_PORT_LOCK  = 3

NMEA_MODE_MAP = {
    NMEA_MODE_DISABLED:   "disabled",
    NMEA_MODE_FIRST_FMT:  "first_format",
    NMEA_MODE_SECOND_FMT: "second_format",
    NMEA_MODE_PORT_LOCK:  "port_lock",
}

ME_ERROR_MODE_DISABLED = 0
ME_ERROR_MODE_NUMERIC  = 1
ME_ERROR_MODE_VERBOSE  = 2

ME_ERROR_MODE_MAP = {
    ME_ERROR_MODE_DISABLED: "disabled",
    ME_ERROR_MODE_NUMERIC:  "numeric",
    ME_ERROR_MODE_VERBOSE:  "verbose",
}

class LE910CXConn(SerialConn):
    """
    Connection class that implements the communication with a LE910CX modem.
    """

    def __init__(self):
        super(LE910CXConn, self).__init__()
        self._startup_settings = {}

    def init(self, settings):
        super(LE910CXConn, self).init(settings)
        self._startup_settings = settings

    def open(self):
        super(LE910CXConn, self).open()
        self.config(self._settings)

    def config(self, settings):
        """
        Configure the modem with passed settings.
        """

        if settings.get("perform_initial_nmea_escape", False):
            self.send_nmea_escape_sequence(wait=True)

        # Configure GNSS
        if "error_config" in settings:
            self.error_config(mode=settings["error_config"])

        if "gnss_session" in settings:
            self.gnss_session(status=settings["gnss_session"])

    def execute(self, cmd, ready_words=["OK"], keep_conn=True, cooldown_delay=None, timeout=None, raise_on_error=True):
        """
        Execute a custom AT command.

        Arguments:
        - cmd (string): The command to be executed.

        Optional arguments:
        - ready_words (list of strings): The ready words to look for - if the function sees those messages from the modem, the command will
          be considered completed and return. Default: `["OK"]`.
        - keep_conn (bool): Whether or not to keep the connection alive after the command has been executed. Default: True.
        - cooldown_delay (number): A number in seconds for which to wait after the command has been executed. Default: None.
        - timeout (number): A timeout in seconds after which the function will terminate. Default: None (falls back to the default timeout for the class).
        - raise_on_error (bool): Set this to true to raise an error when the modem responds with an error. Default: True.
        """

        log.info("Executing AT command: %s", cmd)
        res = None

        try:
            self.write_line(cmd)

            for ready_word in ready_words:
                res = self.read_until(ready_word, error_regex, timeout=timeout)

                if "error" in res:
                    log.error("Command {} returned error {}".format(cmd, res["error"]))
                    break

            log.info("Got result: %s", res)

        finally:
            if not keep_conn:
                log.info("Closing serial connection")
                self.close()

        # Wait if cooldown delay is defined
        if cooldown_delay != None:
            log.info("Sleeps for {:f} seconds according to specified cooldown delay".format(cooldown_delay))
            time.sleep(cooldown_delay)

        # Raise on error
        if raise_on_error and "error" in res:
            raise CommandExecutionException("Command {} returned error {}".format(cmd, res["error"]))

        return res

    def error_config(self, mode=None, force=False):
        """
        Configures the error values the modem returns.

        Optional parameters:
        - mode (string): The mode that should be set to the modem. Passing no mode will read the current configuration.
          Read available modes below. Default: None
        - force (bool): Force apply the configuration to the modem.

        Available modes:
        - disabled: Disable verbose error logging. Modem will return just `ERROR` responses.
        - numeric: Modem will return numerical error values.
        - verbose: Modem will return verbose error values.
        """

        ret = {}
        res = self.execute("AT+CMEE?")

        res_regex = re.compile("\+CMEE: (?P<mode>[0-2])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        ret["mode"] = ME_ERROR_MODE_MAP[int(match.group("mode"))]

        if mode != None:
            # Validate mode
            if type(mode) != str or mode not in ME_ERROR_MODE_MAP.values():
                raise ValueError("'mode' argument needs to be one of {}".format(ME_ERROR_MODE_MAP.values()))

            if ret["mode"] != mode or force:
                mode_val = dict_key_by_value(ME_ERROR_MODE_MAP, mode)
                self.execute("AT+CMEE={:d}".format(mode_val))

                ret["mode"] = mode

        return ret

    def imei(self):
        res = self.execute("AT+GSN=1")
        return re.compile("\\+GSN: (?P<value>[0-9]+)").match(res.get("data", "")).groupdict()

    def manufacturer_id(self):
        ret = {}

        res = self.execute("AT+GMI")
        ret["value"] = res.get("data", None)

        return ret

    def model_id(self):
        ret = {}

        res = self.execute("AT+GMM")
        ret["value"] = res.get("data", None)

        return ret

    def soft_reset(self):
        ret = {}

        self.execute("ATZ")

        return ret

    def reset(self, mode=None, delay=0, help=False):
        # TODO HN: Parse result

        if mode == None:
            return self.execute("AT#ENHRST?")

        return self.execute("AT#ENHRST={:d},{:d}".format(mode, delay))

    def time(self):
        # TODO HN: Parse result

        return self.execute("AT+CCLK?")

    def cell_location(self):
        # TODO HN: Parse result

        return self.execute("AT#GTP")

    def sms_storage(self):

        ret = {}

        res = self.execute("AT+CPMS?")
        re.compile("\\+CPMS: \"(?P<read_mem>[0-1])\"").match(res.get("data", ""))


        ret["mode"] = SMS_FORMAT_MODES.get(int(re.compile("\\+CMGF: (?P<mode>[0-1])").match(res.get("data", "")).group("mode")), None)


    def sms_format(self, mode=None, force=False):
        """
        Configures the SMS format.

        Possible modes:
        - 'pud': PUD mode
        - 'txt': Text mode
        """

        ret = {}

        if not force:
            res = self.execute("AT+CMGF?")
            ret["mode"] = SMS_FORMAT_MODES.get(int(re.compile("\\+CMGF: (?P<mode>[0-1])").match(res.get("data", "")).group("mode")), None)
        elif mode == None:
            raise ValueError("Mode must be specified")

        if mode != None:
            mode = mode.upper()

            if not mode in SMS_FORMAT_MODES.values():
                raise ValueError("Unsupported mode")

            if force or mode != ret["mode"]:
                self.execute("AT+CMGF={:d}".format(dict_key_by_value(SMS_FORMAT_MODES, mode)))
                ret["mode"] = mode

        return ret

    def sms_list(self, status="ALL", clear=False, format_mode="TXT"):
        """
        Returns a list of all SMS messages currently stored on the modem.
        """

        ret = {"values": []}

        # Ensure message format mode
        prev_format_mode = self.sms_format().get("mode", "PUD")
        if prev_format_mode != format_mode:
            self.sms_format(mode=format_mode)

        try:
            res = self.execute("AT+CMGL=\"{:s}\"".format(status))
            for i in range(0, len(res["data"]), 2): # Process every second one - one message is two entries in here
                meta = res["data"][i]
                data = res["data"][i+1]

                index, msg_status, sender, _, date, time = [m.strip("\"") for m in meta[7:].split(",")]

                # NV NOTE: Since the modem stores a time offset value (timezone info) we need to use that
                # to calculate the timestamp to be in UTC. Keep in mind that this calculation has only been
                # tested in a single timezone and more testing might need to be done.

                # example timestamp from modem:    21/11/16,14:10:00+04 (each offset increment equals 15 minutes)
                # utc timestamp after calculation: 2021-11-16T13:10:00
                time_offset_sign = time[-3:-2]
                time_offset = int(time[-2:])
                offset_duration = datetime.timedelta(minutes=(15 * time_offset))

                msg_timestamp = datetime.datetime.strptime("{}T{}".format(date, time[:-3]), "%y/%m/%dT%H:%M:%S")
                if time_offset_sign == "+":
                    msg_timestamp = msg_timestamp - offset_duration
                elif time_offset_sign == "-":
                    msg_timestamp = msg_timestamp + offset_duration
                else:
                    raise Exception("Received an unexpected time offset sign: {}".format(time_offset_sign))

                msg = {
                    "index": int(index), # Casting this, other functions relying on this parameter expect it to be an integer
                    "status": msg_status,
                    "sender": sender,
                    "timestamp": msg_timestamp.isoformat(),
                    "data": data,
                }

                ret["values"].append(msg)
        finally:
            try:
                self.sms_format(mode=prev_format_mode)
            except:
                log.exception("Failed to restore SMS format mode")

        return ret

#    def sms_delete(self, *indexes, all=False, confirm=False):
#        """
#        Deletes SMS message(s) stored on the modem.
#
#        Parameters:
#        - index (number): The index number of the message that should be deleted. Default None.
#        - delete_all (bool): If all messages stored on the modem should be deleted. If this and the `index` parameter
#          aren't provided, then the function will only return the delete-able messages.
#        - confirm (bool): A confirmation flag needed to be provided when deleting messages
#        """
#        if index == None and delete_all == False:
#            # Just list deleteable messages
#            return self.execute("AT+CMGD=?")
#
#        if not confirm:
#            raise salt.exceptions.CommandExecutionError(
#                "This command will delete SMS messages stored on the modem - add parameter 'confirm=true' to continue anyway.")
#
#        if delete_all:
#            log.info("Deleting *ALL* SMS messages stored in the modem's memory.")
#            return self.execute("AT+CMGD=1,4")
#        else:
#            log.info("Deleting message with index {}".format(index))
#            return self.execute("AT+CMGD={},0".format(index))

    def gnss_location(self, decimal_degrees=False):
        """
        Fetches current GPS location and other GPS related metadata from the modem.

        Parameters:
        - decimal_degrees (bool): Whether to return the lat/lon data in DD (decimal degrees) format as opposed to the default
          DMS (degrees, minutes, seconds) format.
        """

        ret = {}
        res = self.execute("AT$GPSACP")

        # Example responses (you can use these for testing)
        # $GPSACP: 093446.000,5702.1608N,00956.1064E,1.4,-30.6,3,0.0,0.0,0.0,140622,04,04
        # $GPSACP: 123748.004,5702.1860N,00956.1058E,2.2,21.1,3,0.0,0.0,0.0,130622,06,00
        # $GPSACP: ,,,,,1,,,,,,           NOTE: Nofix
        res_regex = re.compile("^\$GPSACP: " + \
            "(?P<utc>[0-9]{6}\.[0-9]{3})?," + \
            "(?P<lat>[0-9]{4}\.[0-9]{4}(N|S))?," + \
            "(?P<lon>[0-9]{5}\.[0-9]{4}(W|E))?," + \
            "(?P<hdop>[0-9]+\.?[0-9]*)?," + \
            "(?P<altitude>-?[0-9]+\.?[0-9]*)?," + \
            "(?P<fix>[0-3])," + \
            "(?P<cog>[0-9]+\.[0-9]+)?," + \
            "(?P<spkm>[0-9]+\.[0-9]+)?," + \
            "(?P<spkn>[0-9]+\.[0-9]+)?," + \
            "(?P<date>[0-9]{6})?," + \
            "(?P<nsat_gps>[0-9]{2})?," + \
            "(?P<nsat_glonass>[0-9]{2})?")

        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        if int(match.group("fix")) in [ GNSS_LOCATION_FIX_INVALID_FIX, GNSS_LOCATION_FIX_NO_FIX ]:
            raise NoFixException()

        # Parse response
        time_utc = match.group("utc")
        date_utc = match.group("date")
        ret = {
            "time_utc":     "{}:{}:{}".format(time_utc[0:2], time_utc[2:4], time_utc[4:6]),
            "date_utc":     "20{}-{}-{}".format(date_utc[4:6], date_utc[2:4], date_utc[0:2]), # NOTE: Date can only start from year 2000
            "hdop":         float(match.group("hdop")),
            "alt":          float(match.group("altitude")),
            "fix":          GNSS_LOCATION_FIX_MAP[int(match.group("fix"))],
            "cog":          float(match.group("cog")),
            "sog_km":       float(match.group("spkm")),
            "sog_kn":       float(match.group("spkn")),
            "nsat_gps":     int(match.group("nsat_gps")),
            "nsat_glonass": int(match.group("nsat_glonass")),
        }

        # Calculate decimal degrees if requested
        # dd = deg + min/60 + sec/3600
        if decimal_degrees:
            lat = match.group("lat")
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:-1])

            lon = match.group("lon")
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:-1])

            # TODO NV: Maybe round them?
            ret["lat"] = lat_deg + (lat_min/60)
            ret["lon"] = lon_deg + (lon_min/60)

        else:
            ret["lat"] = match.group("lat")
            ret["lon"] = match.group("lon")

        return ret

    def gnss_session(self, status=None, force=False):
        """
        Gets or sets the GNSS session status (i.e. is the dedicated GPS enabled).

        Optional parameters:
        - status (bool): Set this parameter to a boolean to enable or disable the GNSS session.
        - force (bool): Force setting the settings to the modem.
        """

        ret = {}
        res = self.execute("AT$GPSP?")

        res_regex = re.compile("\\$GPSP: (?P<status>[0-1])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        # NOTE: Have to parse to int first, as any non-empty string will result in a truthy value
        ret["status"] = bool(int(match.group("status")))

        if status != None:
            if type(status) != bool:
                raise TypeError("'status' parameter needs to be of type 'bool'")

            if status != ret["status"] or force:
                self.execute("AT$GPSP={:d}".format(status))
                ret["status"] = status

        return ret

    def gnss_nmea_data_config(self, mode=None, gga=False, gll=False, gsa=False, gsv=False, rmc=False, vtg=False, force=False):
        """
        Gets or sets the NMEA data configuration of the modem.

        Optional arguments:
        - mode (string): One of four available modes: `disabled`, `first_format`, `second_format` or `first_format_lock_port`. The different values are explained
          below. Set this value to `None` (default) to get the current NMEA data configuration.
        - gga (bool): Enables/disables the presence of the Global Positioning System Fix Data NMEA sentence (GGA) in the GNSS data stream.
        - gll (bool): Enable/disable the presence of the Geographic Position - Latitude/Longitude NMEA sentence (GLL) in the GNSS data stream.
        - gsa (bool): Enable/disable the presence of the GNSS DOP and Active Satellites NMEA sentence (GSA) in the GNSS data stream.
        - gsv (bool): Enable/disable the presence of the Satellites in View NMEA sentence (GSV) in the GNSS data stream.
        - rmc (bool): Enable/disable the presence of the Recommended Minimum Specific GNSS Data NMEA sentence (RMC) in the GNSS data stream.
        - vtg (bool): Enable/disable the presence of the GNSS Course Over Ground and Ground Speed NMEA sentence (VTG) in the GNSS data stream.
        - force (bool): Force applying the settings to the modem.

        Available modes:
        - disabled: Disable NMEA data stream.
        - first_format: Enable the first NMEA data stream format.
        - second_format: Enable the second NMEA data stream format.
        - port_lock: Enable the first NMEA data stream format and reserve the interface port only for the NMEA data stream.
        """

        ret = {}
        res = self.execute("AT$GPSNMUN?")

        res_regex = re.compile("^\$GPSNMUN: " + \
                "(?P<mode>[0-3])," + \
                "(?P<gga>[0-1])," + \
                "(?P<gll>[0-1])," + \
                "(?P<gsa>[0-1])," + \
                "(?P<gsv>[0-1])," + \
                "(?P<rmc>[0-1])," + \
                "(?P<vtg>[0-1])"
        )
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from mode: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        # Construct return value
        # NOTE: We need to parse to int first, as any non-empty string will result in a truthy value: bool('0') == True
        ret["mode"] = NMEA_MODE_MAP[int(match.group("mode"))]
        ret["gga"] = bool(int(match.group("gga")))
        ret["gll"] = bool(int(match.group("gll")))
        ret["gsa"] = bool(int(match.group("gsa")))
        ret["gsv"] = bool(int(match.group("gsv")))
        ret["rmc"] = bool(int(match.group("rmc")))
        ret["vtg"] = bool(int(match.group("vtg")))

        if mode != None:
            # Validate mode
            if type(mode) != str or mode not in NMEA_MODE_MAP.values():
                raise ValueError("'mode' argument needs to be one of {}".format(NMEA_MODE_MAP.values()))

            # Validate services
            if type(gga) != bool or \
            type(gll) != bool or \
            type(gsa) != bool or \
            type(gsv) != bool or \
            type(rmc) != bool or \
            type(vtg) != bool:
                raise ValueError("'gga', 'gll', 'gsa', 'gsv', 'rmc' and 'vtg' parameters all need to be of type 'bool'")

            # Determine if we need to execute an extra command
            if ret["mode"] != mode or \
            ret["gga"] != gga or \
            ret["gll"] != gll or \
            ret["gsa"] != gsa or \
            ret["gsv"] != gsv or \
            ret["rmc"] != rmc or \
            ret["vtg"] != vtg or \
            force:
                mode_val = dict_key_by_value(NMEA_MODE_MAP, mode)
                cmd = "AT$GPSNMUN={:d},{:d},{:d},{:d},{:d},{:d},{:d}".format(
                    dict_key_by_value(NMEA_MODE_MAP, mode), bool(gga), bool(gll), bool(gsa), bool(gsv), bool(rmc), bool(vtg))

                if mode_val == NMEA_MODE_PORT_LOCK:
                    res = self.execute(cmd, ready_words=["CONNECT"])
                else:
                    res = self.execute(cmd)

                # Construct return value
                ret["mode"] = mode
                ret["gga"] = bool(gga)
                ret["gll"] = bool(gll)
                ret["gsa"] = bool(gsa)
                ret["gsv"] = bool(gsv)
                ret["rmc"] = bool(rmc)
                ret["vtg"] = bool(vtg)

        return ret

    def nmea_messages(self, timeout=5):
        """
        Read all NMEA messages that have been sent by the modem.

        Optional parameters:
        - timeout (number): The amount of time in seconds to wait for the first message.
          Default 5.
        """

        raw_lines = self.read_lines(timeout)

        if not raw_lines:
            return []

        lines = [ line.strip() for line in raw_lines ]
        return lines

    def send_nmea_escape_sequence(self, wait=False, timeout=3):
        """
        Send NMEA escape sequence to stop unsolicited NMEA messages and unlock
        the ability to send AT commands again.

        Optional parameters:
        - wait (bool): Should the function wait for the modem to send the expected
          response back? If this argument is set to true, the function will
          return all buffered NMEA sentences. Default: False.
        - timeout (number): The amount of time in seconds to wait for the expected
          response. Default 3.
        """

        # Send escape sequence
        self.write("+++")

        if wait:
            # Wait for the port to become available again
            res = self.read_until("NO CARRIER", error_regex, timeout=timeout)
            return res
