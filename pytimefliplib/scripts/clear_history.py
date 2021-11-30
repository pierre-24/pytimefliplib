import argparse

from pytimefliplib.async_client import AsyncClient
from pytimefliplib.scripts import run_on_client


async def actions_on_client(client: AsyncClient, args: argparse.Namespace):
    await client.history_delete()
    print('! Cleared history')


def main():
    run_on_client(
        'Clear history',
        lambda e: e,
        actions_on_client
    )


if __name__ == '__main__':
    main()
