import argparse
from datetime import datetime, timedelta

from pytimefliplib.async_client import AsyncClient
from pytimefliplib.scripts import run_on_client


async def actions_on_client(client: AsyncClient, args: argparse.Namespace):

    # get characteristics
    print('TimeFlip characteristics::')
    print('- Name:', await client.device_name())
    print('- Firmware:', await client.firmware_revision())
    print('- Battery:', await client.battery_level())
    print('- Current facet:', await client.current_facet())
    #print('- Accelerometer vector:', ', '.join('{:.3f}'.format(x) for x in await client.accelerometer_value()))
    print('- Status:', await client.get_status())

    print('Facets::')
    facets = await client.get_all_facets()
    for number, mode, pomodoro, timer in facets:
        print('- Facet={} mode: {}, pomodoro time: {}, timer: {}'
              .format(number, mode, pomodoro, timer)
        )

    #await client.set_facet(1,1,300)

    # print history
    print('History::')
    history = await client.get_all_history()
    for number, facet, orig, duration in history:
        print('- Event {} on facet {} ({} seconds) from {}'.format(number, facet, duration, orig))

    # print event
    event = await client.get_event()
    print("Event: {}", event)


def main():
    run_on_client(
        'Get TimeFlip device characteristics',
        lambda e: e,
        actions_on_client
    )


if __name__ == '__main__':
    main()
