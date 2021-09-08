import argparse

from pytimefliplib.async_client import AsyncClient
from pytimefliplib.scripts import run_on_client


async def actions_on_client(client: AsyncClient, args: argparse.Namespace):

    # get characteristics
    print('TimeFlip characteristics::')
    print('- Name:', await client.device_name())
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


def main():
    run_on_client(
        'Get TimeFlip device characteristics',
        lambda e: e,
        actions_on_client
    )


if __name__ == '__main__':
    main()
