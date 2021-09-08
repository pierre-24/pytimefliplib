import asyncio
import sys
from typing import Dict, List

from bleak import BleakScanner, BleakClient, BleakError
from bleak.backends.device import BLEDevice

from pytimefliplib.async_client import CHARACTERISTICS


async def run():
    """Adapted from Bleak documentation (https://pypi.org/project/bleak/) for the discovery of new devices.
    """

    devices_map: Dict[str, List[BLEDevice]] = {
        'connection_issue': [],
        'not_timeflip': [],
        'timeflip': []
    }

    print('Looking around (this can take up to 1 minute) ...', end='')
    sys.stdout.flush()  # force the above to appear

    devices = await BleakScanner.discover()
    for d in devices:
        try:
            async with BleakClient(d) as client:
                try:  # Check if the device have a TimeFlip characteristic (here, the facet value)
                    _ = await client.read_gatt_char(CHARACTERISTICS['facet'])
                    devices_map['timeflip'].append(d)
                except BleakError:
                    devices_map['not_timeflip'].append(d)

        except (BleakError, asyncio.exceptions.TimeoutError):
            devices_map['connection_issue'].append(d)

    print(' Done!')
    print('Results::')
    print('- TimeFlip devices:', ', '.join('{} ({})'.format(d.address, d.name) for d in devices_map['timeflip']))
    print('- Other BLE devices:', ', '.join('{} ({})'.format(d.address, d.name) for d in devices_map['not_timeflip']))
    print('- Other devices:', ', '.join('{}'.format(d.address) for d in devices_map['connection_issue']))


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


if __name__ == '__main__':
    main()
