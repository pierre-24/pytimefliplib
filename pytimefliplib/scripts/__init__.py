import argparse
import asyncio
import sys

from bleak import BleakError

from typing import Callable, Coroutine

import pytimefliplib
from pytimefliplib.async_client import AsyncClient, DEFAULT_PASSWORD, TimeFlipRuntimeError


class RuntimeClientError(Exception):
    pass


def is_valid_addr(addr: str) -> str:
    """Check if it is a valid MAC address
    """

    seq = addr.split(':')

    if len(seq) != 6:
        raise argparse.ArgumentTypeError('{} is not a valid address'.format(addr))

    try:
        data = [int(x, base=16) for x in seq]
    except ValueError as e:
        raise argparse.ArgumentTypeError(e)

    if not all(0 <= x < 256 for x in data):
        raise argparse.ArgumentTypeError('{} is not a valid address'.format(addr))

    return addr


async def connect_and_run(
        args: argparse.Namespace, actions_on_client: Callable[[AsyncClient, argparse.Namespace], Coroutine]):
    try:
        async with AsyncClient(args.address) as client:
            # setup
            print('! Connected to {}'.format(args.address))

            await client.setup(password=args.password)
            print('! Password communicated')

            await actions_on_client(client, args)

    except (BleakError, TimeFlipRuntimeError, RuntimeClientError) as e:
        print('communication error: {}'.format(e), file=sys.stderr)


def run_on_client(
        doc: str,
        add_extra_arguments: Callable[[argparse.ArgumentParser], None],
        actions_on_client: Callable[[AsyncClient, argparse.Namespace], Coroutine]
) -> None:

    # create parser
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + pytimefliplib.__version__)

    parser.add_argument('-a', '--address', type=is_valid_addr, help='Address of the TimeFlip device', required=True)
    parser.add_argument('-p', '--password', type=str, help='Password', default=DEFAULT_PASSWORD)

    # add extra option
    add_extra_arguments(parser)

    # run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(connect_and_run(parser.parse_args(), actions_on_client))
