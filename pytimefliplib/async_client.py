import asyncio
from bleak import BleakClient
from functools import wraps
from typing import Callable, Any, List, Tuple
import struct

UUID_GENERIC = '0000{:x}-0000-1000-8000-00805f9b34fb'
UUID_TIMEFLIP = 'f119{:x}-71a4-11e6-bdf4-0800200c9a66'

DEFAULT_PASSWORD = '000000'

BLUETOOTH_ENDIANNESS = 'little'
TIMEFLIP_ENDIANNESS = BLUETOOTH_ENDIANNESS  # it was not clear, but based on history read out, it is little endian

CHARACTERISTICS = {
    # generic
    'battery_level': UUID_GENERIC.format(0x2a19),
    'firmware_revision': UUID_GENERIC.format(0x2a26),
    'device_name': UUID_GENERIC.format(0x2a00),

    # timeflip
    'accelerometer_data': UUID_TIMEFLIP.format(0x6f51),
    'facet': UUID_TIMEFLIP.format(0x6f52),
    'command_result': UUID_TIMEFLIP.format(0x6f53),
    'command_input': UUID_TIMEFLIP.format(0x6f54),
    'double_tap': UUID_TIMEFLIP.format(0x6f55),  # "double tap" is reserved for future use
    'calibration_version': UUID_TIMEFLIP.format(0x6f56),
    'password_input': UUID_TIMEFLIP.format(0x6f57)
}


def _com(x):
    return bytearray([x] if type(x) is int else x)


COMMANDS = {
    'history': _com(0x01),
    'history_delete': _com(0x02),
    'calibration_reset': _com(0x03),
    'lock_on': _com([0x04, 0x01]),
    'lock_off': _com([0x04, 0x02]),
    # - auto_pause is 0x05
    'pause_on': _com([0x06, 0x01]),
    'pause_off': _com([0x06, 0x02]),
    'status': _com(0x10),
}


class NotConnectedError(Exception):
    pass


class NotLoggedInError(Exception):
    pass


class TimeFlipCommandError(Exception):

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

    def __init__(self, address: str, loop: asyncio.events.AbstractEventLoop = None):

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

    # basic BLE actions:

    async def connect(self) -> None:
        """Connect to the device
        """

        self.client = BleakClient(self.address)
        self.connected = await self.client.connect()

    @requires_connection
    async def base_char_read(self, uuid: str) -> bytearray:
        """Read characteristic value from uuid

        :param uuid: characteristic uuid
        """
        return await self.client.read_gatt_char(uuid)

    @requires_connection
    async def base_char_write(self, uuid: str, data: bytearray) -> None:
        """Write characteristic value from uuid

        :param uuid: characteristic uuid
        :param data: data to write
        """
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
            await self.base_char_read(CHARACTERISTICS['battery_level']), BLUETOOTH_ENDIANNESS)

    @requires_connection
    async def firmware_revision(self) -> str:
        """Get firmware revision version

        :return: revision version
        """

        return (await self.base_char_read(CHARACTERISTICS['firmware_revision'])).decode('ascii')

    @requires_connection
    async def device_name(self) -> str:
        """Get device name

        :return: device name
        """

        return (await self.base_char_read(CHARACTERISTICS['device_name'])).decode('ascii')

    # client specific characteristics:

    @requires_connection
    async def login(self, password: str = DEFAULT_PASSWORD) -> bool:
        """Put the password in 0x6f57, so that other command can work

        There is no way to know if password is right, though (except getting 0 on other commands),
        so return value is True
        """

        await self.base_char_write(CHARACTERISTICS['password_input'], bytearray(password.encode('ascii')))
        self.logged = True
        return self.logged

    @requires_connection
    async def setup(self, facet_callback: Callable[[str, Any], Any] = None, password: str = DEFAULT_PASSWORD) -> None:
        """
        + Log in,
        + Setup the notification callback on 0x6f52 (if any)
        + Get status to update internals
        + Get current facet (triggers the callback)

        :param facet_callback: callback called every time the facet change.
               Should be of the form ``callback(sender, data)``.
        :param password: password
        :raise NotLoggedInError: if login fails
        """

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
                await self.base_char_read(CHARACTERISTICS['facet']), TIMEFLIP_ENDIANNESS)

        return self.current_facet_value

    @requires_login
    async def calibration_version(self) -> int:
        """Get calibration version. Requires login !

        :return: an integer
        """

        return int.from_bytes(await self.base_char_read(CHARACTERISTICS['calibration_version']), TIMEFLIP_ENDIANNESS)

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

        data = await self.base_char_read(CHARACTERISTICS['accelerometer_data'])
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

        await self.base_char_write(CHARACTERISTICS['command_input'], command)

        # print('command is', command)

        if check:
            data = await self.base_char_read(CHARACTERISTICS['command_input'])
            return data[0] == command[0] and data[-1] == 0x02
        else:
            return True

    @requires_login
    async def write_command_and_read_output(self, command: bytearray, check=False) -> bytearray:
        """Write a command (in 0x6f54), and then read result (in 0x6f53). Requires login !
        """

        went_ok = await self.write_command(command, check)
        if not went_ok:
            raise TimeFlipCommandError(command)

        return await self.base_char_read(CHARACTERISTICS['command_result'])

    @requires_login
    async def status(self) -> dict:
        """Get status (command 0x10) on pause, lock and auto-pause. Requires login !

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
    async def history(self) -> List[Tuple[int, int, bytearray]]:
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
            data = await self.base_char_read(CHARACTERISTICS['command_result'])

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
