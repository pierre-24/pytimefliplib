import argparse

from pytimefliplib.async_client import AsyncClient
from pytimefliplib.scripts import run_on_client, RuntimeClientError


def add_extra_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('new_password', type=str, help='New device password')


async def actions_on_client(client: AsyncClient, args: argparse.Namespace):

    # print out
    if await client.set_password(args.new_password):
        print('! Changed password to "{}"'.format(args.new_password))
    else:
        raise RuntimeClientError('Something went wrong while changing password')


def main():
    run_on_client(
        'Set a new name password on the device',
        add_extra_arguments,
        actions_on_client
    )


if __name__ == '__main__':
    main()
