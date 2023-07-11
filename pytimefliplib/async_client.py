from bleak import BleakClient
from functools import wraps
from typing import Callable, Any, List, Tuple
import struct

TWENTY_ZEROES = [ 0x00, 0x00, 0x00, 0x00, 0x00, 
                  0x00, 0x00, 0x00, 0x00, 0x00, 
                  0x00, 0x00, 0x00, 0x00, 0x00, 
                  0x00, 0x00, 0x00, 0x00, 0x00 ]

UUID_GENERIC = '0000{:x}-0000-1000-8000-00805f9b34fb'
UUID_TIMEFLIP = 'f119{:x}-71a4-11e6-bdf4-0800200c9a66'

DEFAULT_PASSWORD = '000000'

BLUETOOTH_ENDIANNESS = 'little'
#TIMEFLIP_ENDIANNESS = BLUETOOTH_ENDIANNESS  # it was not clear, but based on history read out, it is little endian
TIMEFLIP_ENDIANNESS = 'big'

CHARACTERISTICS = {
    # generic
    'battery_level':        UUID_GENERIC.format(0x2a19),
    'firmware_revision':    UUID_GENERIC.format(0x2a26),
    'device_name':          UUID_GENERIC.format(0x2a00),

    # timeflip
    'event_data':           UUID_TIMEFLIP.format(0x6f51), # vers 4.0
    'accelerometer_data':   UUID_TIMEFLIP.format(0x6f51), # vers 3.0
    'facet':                UUID_TIMEFLIP.format(0x6f52),
    'command_result':       UUID_TIMEFLIP.format(0x6f53),
    'command_input':        UUID_TIMEFLIP.format(0x6f54),
    'double_tap':           UUID_TIMEFLIP.format(0x6f55),  # "double tap" is reserved for future use
    'calibration_version':  UUID_TIMEFLIP.format(0x6f56), # vers 3.0
    'system_state':         UUID_TIMEFLIP.format(0x6f56), # vers 4.0
    'password_input':       UUID_TIMEFLIP.format(0x6f57),
    'history_data':         UUID_TIMEFLIP.format(0x6f58),
}

# This is per the v 4.0 specification
CHARACTERISTIC_READ_LENGTHS = {
    # generic
    'battery_level':        1,
    'firmware_revision':    20,
    'device_name':          20,

    # timeflip
    'event_data':           20,
    'accelerometer_data':   -1, # deprecated
    'facet':                1,
    'command_result':       20,
    'command_input':        2,
    'double_tap':           -1,
    'system_state':         4,
    'calibration_version':  -1, # deprecated
    'password_input':       -1,
    'history_data':         20
}

CHARACTERISTIC_WRITE_LENGTHS = {
    # generic
    'battery_level':        -1,
    'firmware_revision':    -1,
    'device_name':          -1,

    # timeflip
    'event_data':           -1,
    'accelerometer_data':   -1, # deprecated
    'facet':                -1,
    'command_result':       -1,
    'command_input':        20,
    'double_tap':           -1,
    'system_state':         -1,
    'calibration_version':  -1, # deprecated
    'password_input':       6,
    'history_data':         20
}

def _com(x):
    return bytearray([x] if type(x) is int else x)


COMMANDS = {
    'history':              _com(0x01),
    'history_delete':       _com(0x02), # version 3
    'history_dump':         _com(0x02), # version 4
    'calibration_reset':    _com(0x03),
    'lock_on':              _com([0x04, 0x01]),
    'lock_off':             _com([0x04, 0x02]),
    'auto_pause_set':       _com(0x05),
    'pause_on':             _com([0x06, 0x01]),
    'pause_off':            _com([0x06, 0x02]),
    'time_read':            _com(0x07),
    'time_write':           _com(0x08),
    'brightness_set':       _com(0x09),
    'blink_freq_set':       _com(0x0A),
    'status':               _com(0x10),
    'color_set':            _com(0x11),
    'facet_write':          _com(0x13),
    'facet_read':           _com(0x14),
    'set_password':         _com(0x30)
}


class TimeFlipRuntimeError(Exception):
    pass


class NotConnectedError(TimeFlipRuntimeError):
    def __init__(self):
        super().__init__('Not connected to device')


class NotLoggedInError(TimeFlipRuntimeError):
    def __init__(self):
        super().__init__('Not logged in (incorrect password?)')

class IncorrectPasswordError(TimeFlipRuntimeError):
    def __init__(self):
        super().__init__('Incorrect password for device')

class TimeFlipCommandError(TimeFlipRuntimeError):

    def __init__(self, command):
        super().__init__('Error while executing {}'.format(command))


def requires_connection(f):
    """Wrapper to force connection if needed
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not args[0].connected:
            raise NotConnectedError()

        return f(*args, **kwargs)

    return wrapper


def requires_login(f):
    """Wrapper to force login if needed
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not args[0].logged:
            raise NotLoggedInError()

        return f(*args, **kwargs)

    return wrapper


class AsyncClient:
    """TimeFlip asynchronous client
    """

    def __init__(self, address: str):

        self.address = address
        self.client = None

        # timeflip states
        self.logged = False
        self.connected = False
        self.facet_callback = None

        self.paused = False
        self.locked = False
        self.auto_pause_time = 0
        self.current_facet_value = -1

        self.firmware_version = None

    # basic BLE actions:

    async def connect(self) -> None:
        """Connect to the device
        """

        self.client = BleakClient(self.address)
        self.connected = await self.client.connect()

    @requires_connection
    async def base_char_read(self, characteristic: str) -> bytearray:
        """Read characteristic value from uuid

        :param uuid: characteristic uuid
        """
        if characteristic not in CHARACTERISTICS:
            raise ValueError("Invalid characteristic")
        
        uuid = CHARACTERISTICS[characteristic]
        length = CHARACTERISTIC_READ_LENGTHS[characteristic]

        if length == -1:
            raise ValueError("Characteristic not supported for read")

        result = await self.client.read_gatt_char(uuid)

        return result[:length]

    @requires_connection
    async def base_char_write(self, characteristic: str, data: bytearray) -> None:
        """Write characteristic value from uuid

        :param uuid: characteristic uuid
        :param data: data to write
        """
        if characteristic not in CHARACTERISTICS:
            raise ValueError("Invalid characteristic")
        
        uuid = CHARACTERISTICS[characteristic]
        length = CHARACTERISTIC_WRITE_LENGTHS[characteristic]

        if length == -1:
            raise ValueError("Characteristic not supported for write")
        # elif len(data) != length:
        #     raise ValueError("Incorrect write length provided")
        
        await self.client.write_gatt_char(uuid, data)

    @requires_connection
    async def disconnect(self) -> None:
        """
        Disconnect from the client.
        Also stop the notification on 0x6f52 before.
        """

        if self.facet_callback:
            try:
                await self.client.stop_notify(CHARACTERISTICS['facet'])
            except (KeyboardInterrupt, SystemExit):
                raise
            except:  # noqa
                pass

        try:
            await self.client.disconnect()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # noqa
            pass

    # client basic characteristics:

    @requires_connection
    async def battery_level(self) -> int:
        """Get the battery level

        :return: percentage of battery level (from 0 to 100)
        """

        return int.from_bytes(
            await self.base_char_read('battery_level'), BLUETOOTH_ENDIANNESS)

    @requires_connection
    async def firmware_revision(self) -> str:
        """Get firmware revision version

        :return: revision version
        """

        return (await self.base_char_read('firmware_revision')).decode('ascii')

    @requires_connection
    async def device_name(self) -> str:
        """Get device name

        :return: device name
        """

        return (await self.base_char_read('device_name')).decode('ascii')

    # client specific characteristics:

    @requires_connection
    async def login(self, password: str = DEFAULT_PASSWORD) -> bool:
        """Put the password in 0x6f57, so that other command can work

        There is no way to know if password is right, though (except getting 0 on other commands),
        so return value is True
        """

        await self.base_char_write('password_input', bytearray(password.encode('ascii')))
        self.logged = True
        return self.logged

    @requires_connection
    async def setup(self, facet_callback: Callable[[str, Any], Any] = None, password: str = DEFAULT_PASSWORD) -> None:
        """
        + Get firmware version
        + Log in,
        + Setup the notification callback on 0x6f52 (if any)
        + Get status to update internals
        + Get current facet (triggers the callback)

        :param facet_callback: callback called every time the facet change.
               Should be of the form ``callback(sender, data)``.
        :param password: password
        :raise NotLoggedInError: if login fails
        """

        # Firmware string like FW_vX.XX, so get a useable
        # float value to compare against
        firmware_revision = await self.firmware_revision()
        self.firmware_version = float(firmware_revision[5:8])

        if not await self.login(password):
            raise NotLoggedInError()

        def custom_facet_callback(sender, data):
            self.current_facet_value = int.from_bytes(data, TIMEFLIP_ENDIANNESS)
            if self.facet_callback:
                self.facet_callback(self.current_facet_value)

        if facet_callback:
            self.facet_callback = facet_callback

        await self.client.start_notify(CHARACTERISTICS['facet'], custom_facet_callback)

        current_status = await self.status()
        self.paused = current_status['paused']
        self.locked = current_status['locked']
        self.auto_pause_time = current_status['auto_pause_time']

        self.current_facet_value = await self.current_facet(force=True)

    @requires_login
    async def current_facet(self, force: bool = False) -> int:
        """Get current facet. Requires login !

        :param force: query the current facet, does not use the cached version
        :return: an integer between 0 and 47 (website says 32, though)
        """

        if force:
            self.current_facet_value = int.from_bytes(
                await self.base_char_read('facet'), TIMEFLIP_ENDIANNESS)

        return self.current_facet_value

    @requires_login
    async def calibration_version(self) -> int:
        """Get calibration version. Requires login !

        :return: an integer
        """

        return int.from_bytes(await self.base_char_read('calibration_version'), TIMEFLIP_ENDIANNESS)

    @requires_login
    async def set_calibration_version(self, version: int) -> None:
        """Set calibration version

        :param version: the version (any number on 4 bytes)
        """

        if version >= 2**32:
            raise ValueError('{} is too large (should be 4 bytes max)'.format(version))

        await self.base_char_write(
            CHARACTERISTICS['calibration_version'], bytearray(int.to_bytes(version, 4, TIMEFLIP_ENDIANNESS)))

    @requires_login
    async def accelerometer_value(self, multiplier: float = 1.0) -> Tuple[float, float, float]:
        """Get accelerometer vector

        .. note::

            By reading the text on the chip, I found out it is (probably) a
            `LIS3DH accelerometer <https://www.st.com/resource/en/datasheet/lis3dh.pdf>`_, (probably) operating at 2G
            (since value should be about ``(0.0, 0.0, 1.0)`` when the chip is on a flat surface).
            Values are thus **little**-endian (documentation says big!) signed values, that needs to be divided by
            16384 to give the acceleration (= gravity) vector in unit of G (= 9.81 m/s²).

            (See the CircuitPython
            `code <https://github.com/adafruit/Adafruit_CircuitPython_LIS3DH/blob/master/adafruit_lis3dh.py>`_
            for more details)

        :param multiplier: multiply all values of the vector
               (if one wants to get acceleration in standard units, put 9.81 as a value).
        :return: accelerometer vector, in unit of G.
        """

        divider = 2**14

        data = await self.base_char_read('accelerometer_data')
        ax, ay, az = struct.unpack('<hhh', data)

        return ax / divider * multiplier, ay / divider * multiplier, az / divider * multiplier

    # commands:

    @requires_login
    async def write_command(self, command: bytearray, check=True) -> bool:
        """Write a command to 0x6f54. Requires login !

        :param command: the command
        :param check: check, through a read in 0x6f54, that command went ok
        :return: True if command was ok, false otherwise. If `check` is false, return is always true
        """
        await self.base_char_write('command_input', command)

        if check:
            data = await self.base_char_read('command_input')
            # First byte should contain the command, second byte should
            # contain the status code. Everything else is unpredictable
            # junk.
            return data[0] == command[0] and data[1] == 0x02
        else:
            return True

    @requires_login
    async def write_command_and_read_output(self, command: bytearray, check=False) -> bytearray:
        """Write a command (in 0x6f54), and then read result (in 0x6f53). Requires login !

        If len of result is not 21, the password is probably incorrect, so raises ``NotLoggedInError``
        """

        went_ok = await self.write_command(command, check)
        if not went_ok:
            raise TimeFlipCommandError(command)

        data = await self.base_char_read('command_result')

        # Note: for version 3.0 this response is expected
        # to be 21 bytes, but for newer it is expected to be
        # 20 bytes

        return data

    @requires_login
    async def status(self) -> dict:
        """Get status (command 0x10) on pause, lock and auto-pause. Requires login !

        If not logged in properly, the data size is not 21, so raises ``NotLoggedIn``

        :return: a dict containing the pause, lock and auto-pause status
        """

        data = await self.write_command_and_read_output(COMMANDS['status'])

        return {
            'locked': data[0] == 0x01,
            'paused': data[1] == 0x01,
            'auto_pause_time': int.from_bytes(data[2:4], TIMEFLIP_ENDIANNESS)
        }

    @requires_login
    async def pause(self, state: bool, force: bool = False) -> bool:
        """Set (or unset) pause (command 0x04). Update internal. Requires login.

        .. note::

            Pausing does not prevent facet to be notified.
            It just change the corresponding history facet value to 63.

        :param state: if state is true, set pause, if it is false, unset pause
        :param force: force command (otherwise, the command is not executed is the state correspond to ``self.paused``)
        :return: the new state (should match ``state``)
        """

        if force or state != self.paused:
            await self.write_command(COMMANDS['pause_on' if state else 'pause_off'], check=True)
            self.paused = state

        return self.paused

    @requires_login
    async def lock(self, state: bool, force: bool = False) -> bool:
        """Set (or unset) lock (command 0x06). Update internal. Requires login.

        .. note::

            Locking **does prevent** facet to be notified.
            Unlocking triggers the callback if facet was changed during lock.

        :param state: if state is true, set lock, if it is false, unset lock
        :param force: force command (otherwise, the command is not executed is the state correspond to ``self.locked``)
        :return: the new state (should match ``state``)
        """

        if force or state != self.locked:
            await self.write_command(COMMANDS['lock_on' if state else 'lock_off'])
            self.locked = state

        return self.locked

    """
    Set Auto Pause command. Used to set the number of minutes until the
    timeflip automatically pauses a timer for a given side. 
    
    Default value is 5 minutes. If this value is set to 0, the timer
    does not automatically pause.

    Written to the command_input characeristics (3 bytes):
        0x05 0xXX 0xXX

        0x05 - command code
        0xXX 0xXX - number of minutes until automatic pause
    """
    @requires_login
    async def set_auto_pause(self, time: int) -> None:
        """Set auto-pause (command 0x05).

        .. warning::

            I was not able to make this work (or I did not understand its purpose).

        :param: time (in minute) after which the timeflip should pause (any number on two bytes)
        """

        if time >= 2**16:
            raise ValueError('time should be only two bytes')

        command = bytearray([0x05])
        command.extend(int.to_bytes(time, 2, TIMEFLIP_ENDIANNESS))
        await self.write_command(command, check=True)
        self.auto_pause_time = time

    @requires_login
    async def set_name(self, name: str) -> bool:
        """Set a new name to the device (0x15)
        """

        name = name.encode('ascii')
        if len(name) > 19:
            raise ValueError('"{}" is too long'.format(name))

        command = [0x15, len(name)]
        command.extend(name)
        return await self.write_command(_com(command), check=True)

    @requires_login
    async def set_password(self, password: str) -> bool:
        """Set a new password (0x30)

        :param password: 6-letter long password
        """

        password = password.encode('ascii')
        if len(password) != 6:
            raise ValueError('Password should be 6 letter long')

        command = [0x30]
        command.extend(password)
        return await self.write_command(_com(command), check=True)
    
    """
    Get Time, reads the internal clock of the Timeflip. 

    Written to the command_input characteristic (1 byte):
        0x07

        0x07 - command code
    
    Read from the command_result characteristic (5 bytes):
        0x07 0xXX 0xXX 0xXX 0xXX

        0x07 - command code
        0xXX 0xXX 0xXX 0xXX - 64-bit integer containing the number of
               seconds since 1970
    """
    @requires_login
    async def get_time(self) -> int:
        pass

    """
    Set Time, sets the internal clock of the Timeflip. 

    Written to the command_input characteristic (5 bytes):

        0x08 - command code
        0xXX - 64-bit integer containing the number of 
        0xXX   seconds since 1970    
        0xXX 
        0xXX
               
    """
    @requires_login
    async def set_time(self, time) -> None:
        pass

    """
    Set Brightness, sets the brightness of the Timeflip LEDs.

    Written to the command_input characteristic (2 bytes):

        0x09 - command code
        0xXX - brightness percent, (0 - 100)

    """
    @requires_login
    async def set_brightness(self, brightness) -> None:
        pass

    """
    Set Blink Frequency, sets the delay between conseutive LED flashes
    from the Timeflip

    Written to the command_input characteristic (2 bytes):

        0x0A - command code
        0xXX - delay in seconds, (5 - 60)

    """
    @requires_login
    async def set_blink_frequency(self, blink_frequency) -> None:
        pass

    """
    Set Facet Color, sets the color in RGB format for a given facet
    of the Timeflip.

    Written to the command_input characteristic (7 bytes):

        0x11 - command code
        0xNN - facet to set the color of (0-24)
        0xRR - amount of red (0-255)
        0xGG - amount of green (0-255)
        0xBB - amount of blue (0-255)

    """
    @requires_login
    async def set_color(self, facet: int, rgb: Tuple[int, int, int]):
        pass

    """
    Set Facet command. Used to set the mode of a given facet and the pomodoro
    time limit, if it is in pomodoro mode.

    Written to the command_input characteristic (7 bytes):

        0x13 0xNN 0xPP 0xTT 0xTT 0xTT 0xTT

        0x13 - command code
        0xNN - facet number (0 - 24)
        0xPP - mode 
            0 for normal
            1 for pomodoro
        0xTT 0xTT 0xTT 0xTT - 64-bit unsigned integer for the pomodoro
                              timer limit in seconds

    """
    @requires_login
    async def set_facet(self, facet: int, mode: int, pomodoro: int) -> None:
        command = bytearray(7)
        command[0] = int.from_bytes(COMMANDS['facet_write'], 'big')
        command[1] = facet
        command[2] = mode
        command[3:6] = pomodoro.to_bytes(4, 'big')

        await self.write_command(command, True)

        del command[:]

    @requires_login
    async def read_facet(self, facet: int) -> Tuple[int, int, int]:
        command = bytearray(2)
        command[0] = int.from_bytes(COMMANDS['facet_read'], 'big')
        command[1] = facet

        data = await self.write_command_and_read_output(command, True)
        del command[:]

        return (
            data[1],
            data[2],
            int.from_bytes(data[3:7], TIMEFLIP_ENDIANNESS),
            int.from_bytes(data[7:11], 'big')
        )

    @requires_login
    async def read_all_facets(self) -> List[Tuple[int, int, int]]:
        data = []

        for i in range(0,12):
            facet_data = await self.read_facet(i)
            data.append(facet_data)

        return data

    @requires_login
    async def event(self) -> str:
        return str(await self.base_char_read('event_data'))

    @requires_login
    async def history(self) -> List[Tuple[int, int, int, int]]:
        """Get the history

        .. note::

            A history package is represented as a tuple of the form ``(facet, duration, original_package)``,
            where ``duration`` is the duration during which the facet was set to this position.
            ``original_package`` contains the original encoded package (if needed).
            Each history read out add a history package, so it can result in multiple time the same facet.

        :return: a list of history packages
        """
        event_number = 0

        _17zeros = bytearray(17)  # mark the end of history

        history_blocks = []

        while True:
            command = bytearray(5)
            command[0] = 0x01
            command[1:5] = event_number.to_bytes(4,'big')

            await self.base_char_write('history_data', command)

            data = await self.base_char_read('history_data')

            print(
                ''.join('{:02x}'.format(x) for x in data[0:4])   + "|" +
                ''.join('{:02x}'.format(data[4]))                + "|" +
                ''.join('{:02x}'.format(x) for x in data[5:13])  + "|" +
                ''.join('{:02x}'.format(x) for x in data[13:18])
            )

            if data == _17zeros:
                break

            history_blocks.append((
                int.from_bytes(data[0:4], TIMEFLIP_ENDIANNESS),  # event number
                data[4],
                int.from_bytes(data[5:13], TIMEFLIP_ENDIANNESS), # timestamp of flip(?)
                int.from_bytes(data[13:18], 'little') # duration of flip
            ))
            
            
            #increment bytes
            event_number = event_number + 1
            del command[:]


        #num_blocks = int.from_bytes(first_pack, TIMEFLIP_ENDIANNESS)
        return history_blocks

    @requires_login
    async def history_v3(self) -> List[Tuple[int, int, bytearray]]:
        """Get the history

        .. note::

            A history package is represented as a tuple of the form ``(facet, duration, original_package)``,
            where ``duration`` is the duration during which the facet was set to this position.
            ``original_package`` contains the original encoded package (if needed).
            Each history read out add a history package, so it can result in multiple time the same facet.

        :return: a list of history packages
        """

        await self.write_command(COMMANDS['history'])

        _21zeros = bytearray(21)  # mark the end of history

        history_blocks = []
        first_pack = None

        while True:
            data = await self.base_char_read('command_result')

            if data == _21zeros:
                break

            first_pack = data[0:2]

            for i in range(7):
                dx = data[i * 3:(i + 1) * 3]
                dxe = dx.copy()
                dxe[2] = ((dx[2] << 6) % 2**8) >> 6  # TODO: there is probably a shorter way
                history_blocks.append((int(dx[2] >> 2), int.from_bytes(dxe, TIMEFLIP_ENDIANNESS), dx))

        num_blocks = int.from_bytes(first_pack, TIMEFLIP_ENDIANNESS)
        return history_blocks[:num_blocks]

    @requires_login
    async def history_delete(self) -> None:
        """Remove history (command 0x02)
        """

        await self.write_command(COMMANDS['history_delete'])

    @requires_login
    async def calibration_reset(self) -> None:
        """Reset calibration (command 0x03)
        """

        await self.write_command(COMMANDS['calibration_reset'])

    # async contexts:

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
