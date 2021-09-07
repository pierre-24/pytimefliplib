import argparse


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
