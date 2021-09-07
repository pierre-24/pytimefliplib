import argparse

from pytimefliplib.async_client import AsyncClient
from pytimefliplib.scripts import run_on_client, RuntimeClientError


def add_extra_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('name', type=str, help='New device name')


async def actions_on_client(client: AsyncClient, args: argparse.Namespace):

    # get name
    current_name = await client.device_name()

    # print out
    if await client.set_name(args.name):
        print('! Changed device name from "{}" to "{}"'.format(current_name, await client.device_name()))
    else:
        raise RuntimeClientError('Something went wrong while changing name')


def main():
    run_on_client('Set a new name for the TimeFlip device', add_extra_arguments, actions_on_client)


if __name__ == '__main__':
    main()
