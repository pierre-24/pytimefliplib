import argparse
import asyncio
import sys

from bleak import BleakError

import pytimefliplib
from pytimefliplib.async_client import AsyncClient
from pytimefliplib.async_client import DEFAULT_PASSWORD
from pytimefliplib.scripts import is_valid_addr


class CommunicationError(Exception):
    pass


def get_arguments_parser():
    parser = argparse.ArgumentParser(description=pytimefliplib.__doc__)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + pytimefliplib.__version__)

    parser.add_argument('address', type=is_valid_addr, help='Address of the TimeFlip device')
    parser.add_argument('-p', '--password', type=str, help='Password', default=DEFAULT_PASSWORD)

    return parser


async def async_main():
    args = get_arguments_parser().parse_args()

    try:
        async with AsyncClient(args.address) as client:
            # setup
            print('! Connected to {}'.format(args.address))

            if await client.device_name() != 'TimeFlip':
                raise CommunicationError('This does not seems to be a TimeFlip device')

            await client.setup(password=args.password)
            print('! Set up password')

            # get characteristics
            print('TimeFlip characteristics::')
            print('- Firmware:', await client.firmware_revision())
            print('- Battery:', await client.battery_level())
            print('- Calibration:', await client.calibration_version())
            print('- Current facet:', await client.current_facet())
            print('- Accelerometer vector:', ', '.join('{:.3f}'.format(x) for x in await client.accelerometer_value()))
            print('- Status:', await client.status())

            # print history
            print('History::')
            for facet, duration, _ in await client.history():
                print('- Facet={}, during {} seconds'.format(facet, duration))

    except (BleakError, CommunicationError) as e:
        print('communication error: {}'.format(e), file=sys.stderr)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == '__main__':
    main()
