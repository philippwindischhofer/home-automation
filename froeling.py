import socket, ctypes, time, datetime, timeutils
from socket import AF_UNSPEC, SOCK_STREAM

class LambdatronicS3100:

    def __init__(self, host, port, timeout = 0.1, debug = True):
        self.debug = debug
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = self._init_socket(host, port, timeout)

        self.init_complete = False
        self.date_time = {"last_updated": "Never"}
        
        self.parameter_names = []
        self.parameter_formats = {}
        self.parameter_values = {"last_updated": "Never"}

    def _init_socket(self, host, port, timeout):
        for res in socket.getaddrinfo(host, port, AF_UNSPEC, SOCK_STREAM):
            af, sock_type, proto, canon_name, sa = res
            
            try:
                sock = socket.socket(af, sock_type, proto)
            except socket.error:
                continue
            
            try:
                sock.settimeout(self.timeout)
                sock.connect(sa)
            except socket.error:
                sock.close()
                continue            
            break

        return sock
        
    def _calculate_checksum(self, frame):
        checksum = sum(frame)
        checksum = ctypes.c_uint16(checksum).value # truncate to 16 bit unsigned
        return checksum.to_bytes(2, byteorder = "big", signed = False)

    def _verify_checksum(self, frame):
        exp = self._calculate_checksum(frame[:-2])
        obs = frame[-2:]
        return exp == obs

    def _buffer_to_string(self, inbuf):
        return " ".join(map(hex, inbuf))

    def _bytes_to_U16(self, inbuf):
        return int.from_bytes(inbuf, byteorder = "big", signed = False)

    def _bytes_to_L16(self, inbuf):
        return int.from_bytes(inbuf, byteorder = "big", signed = True)
    
    def _decode_cp850(self, inbuf):
        return inbuf.decode('cp850')
    
    def _send_frame(self, tx_frame):
        if not isinstance(tx_frame, bytes):
            tx_frame = bytes(tx_frame)
            
        checksum = self._calculate_checksum(tx_frame)
        full_frame = tx_frame + checksum

        if self.debug:
            print("TX: " + self._buffer_to_string(full_frame))
        
        return self.sock.send(full_frame)

    def _recv_bytes(self, num_bytes):
        inbuf = self.sock.recv(num_bytes)

        while True:
            diff = num_bytes - len(inbuf)

            if diff == 0:
                return inbuf
            
            inbuf += self.sock.recv(diff)
    
    def _receive_frame(self):
        
        try:
            header_bytes = 3
            header = self._recv_bytes(header_bytes)

            if len(header) != header_bytes:
                raise ConnectionError("Error: communication failure")
            
            frame_len = header[2]
            payload = self._recv_bytes(frame_len + 2) # including 2 checksum bytes

            full_frame = header + payload
            
            if self.debug:
                print("RX: " + self._buffer_to_string(full_frame))
                print("Header: {}, Payload: {}".format(self._buffer_to_string(header),
                                                       self._buffer_to_string(payload)))

            return full_frame
                  
        except TimeoutError:
            return None

    def _split_frame(self, frame):
        command = frame[:2]
        frame_len = frame[2]
        payload = frame[3 : 3 + frame_len]
        checksum = frame[-2:]

        assert len(command) + 1 + len(payload) + len(checksum) == len(frame)
        return command, payload
        
    def _receive_validate_frame(self):
        frame = self._receive_frame()
        if frame is None:
            return None

        if self._verify_checksum(frame):
            return frame
        else:
            return None
        
    def _send_ack(self, cmd):
        frame = cmd + bytes([0x01, 0x01])
        return self._send_frame(frame)

    def _is_ack(self, payload):
        return len(payload) == 1 and payload[0] == 0x01

    def _parse_bcd(self, byte):
        return (byte >> 4) * 10 + (byte & 0x0F)
    
    def _parse_date_time(self, payload):

        if not len(payload) == 7:
            return

        seconds = self._parse_bcd(payload[0])
        minutes = self._parse_bcd(payload[1])
        hours = self._parse_bcd(payload[2])
        day = self._parse_bcd(payload[3])
        month = self._parse_bcd(payload[4])
        weekday = payload[5] 
        year = 2000 + self._parse_bcd(payload[6])

        self.date_time["date_time"] = timeutils.get_timestamp(datetime.datetime(year, month, day, hours, minutes, seconds))
        self.date_time["last_updated"] = timeutils.get_current_timestamp()

    def _parse_parameter_names(self, payload):

        parameter_name = {}

        if payload[0] == 0x53:
            parameter_name["type"] = "string"
        elif payload[0] == 0x49:
            parameter_name["type"] = "value"
        else:
            parameter_name["type"] = "other"

        parameter_name["index"] = self._bytes_to_U16(payload[1:3])
        parameter_name["unknown"] = self._bytes_to_U16(payload[3:5])
        parameter_name["name"] = self._decode_cp850(payload[5:]).strip()
        
        self.parameter_names.append(parameter_name)

    def _parse_parameter_format(self, payload):

        if not len(payload) == 8:
            raise ConnectionError("Wrong payload length")

        index = self._bytes_to_U16(payload[0:2])
        parameter_format = {
            "unit": self._decode_cp850(payload[2:3]),
            "num_decimals": payload[3],
            "divisor": self._bytes_to_U16(payload[4:6]),
            "unknown": self._bytes_to_U16(payload[6:])
        }

        self.parameter_formats[index] = parameter_format

    def _parse_parameter(self, ind, param_buf):        
        cur_param_name = self.parameter_names[ind]
        cur_param_ind = cur_param_name["index"]
        cur_param_format = self.parameter_formats[cur_param_ind]
        
        if cur_param_name["type"] == "value":            
            cur_param_val = self._bytes_to_L16(param_buf) / cur_param_format["divisor"]
            self.parameter_values[cur_param_name["name"]] = cur_param_val
        else:
            if self.debug:
                print("Reading display texts not currently supported")
        
    def _parse_measurements(self, payload):
        
        def chunk(inlist, chunk_length):
            for cur_chunk in range(0, len(inlist), chunk_length):
                yield inlist[cur_chunk:cur_chunk + chunk_length]

        if not len(payload) == 2 * len(self.parameter_names):
            raise ConnectionError("Wrong payload length")
                
        for ind, cur_param_buf in enumerate(chunk(payload, 2)):
            self._parse_parameter(ind, cur_param_buf)

        self.parameter_values["last_updated"] = timeutils.get_current_timestamp()
        
    def _parse_cmd(self, cmd, payload):
        if not cmd[0] == 0x4D:
            if self.debug:
                print("Unknown command: " + self._buffer_to_string(cmd))

        cmd_selector = cmd[1]
        if cmd_selector == 0x31:
            # M1 command: measurements
            self._parse_measurements(payload)
        elif cmd_selector == 0x32:
            # M2 command: time
            self.init_complete = True # once time is sent, everything is fully initialized
            self._parse_date_time(payload)
        elif cmd_selector == 0x33:
            # M3 command: error messages
            pass
        elif cmd_selector == 0x41:
            # MA command: description of measurements
            self._parse_parameter_names(payload)
        elif cmd_selector == 0x42:
            # MB command: display texts
            pass
        elif cmd_selector == 0x43:
            # MC command: formatting of measurements
            self._parse_parameter_format(payload)
        else:
            if self.debug:
                print("Command {} currently not supported".format(cmd_selector))
    
    def send_login(self, mode = "customer"):
        frame = [0x52, 0x61, 0x03, 0x00]
        
        if mode == "customer":
            frame += [0x00, 0x01]
        elif mode == "service":
            frame += [0xff, 0xf9]
        else:
            raise RuntimeError(f"Mode '{mode}' not available")

        return self._send_frame(frame)

    def request_status(self):
        frame = [0x52, 0x62, 0x03, 0x00, 0x00, 0x00]
        return self._send_frame(frame)
    
    def receive_and_parse(self):

        frame = self._receive_validate_frame()
        if frame is None:
            return False

        cmd, payload = self._split_frame(frame)

        if self._is_ack(payload):
            return False

        self._send_ack(cmd)
        self._parse_cmd(cmd, payload)
        return True
        
if __name__ == "__main__":

    froeling = LambdatronicS3100(host = '192.168.1.147', port = 23, debug = False)

    # initialize everything
    froeling.send_login(mode = "service")
    while True:
        froeling.receive_and_parse()
        if froeling.init_complete:
            break
        
    if froeling.debug:
        for ind, parameter_name in enumerate(froeling.parameter_names):
            print("----")
            print("{} ({}):  {} ({})".format(parameter_name["index"], ind, parameter_name["name"],
                                             parameter_name["type"]))
            
            mcind = parameter_name["index"]
            print("Unit: {}, Num decimals: {}, Divisor: {}".format(froeling.parameter_formats[mcind]["unit"],
                                                                   froeling.parameter_formats[mcind]["num_decimals"],
                                                                   froeling.parameter_formats[mcind]["divisor"]))
            print("----")

    # request measurements
    froeling.request_status()
    while True:
        while True:
            if not froeling.receive_and_parse():
                print(froeling.date_time)
                print(froeling.parameter_values)
                break
