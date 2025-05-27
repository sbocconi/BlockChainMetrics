from .blockchain_metrics import calculate_metrics

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '-f', '--filename',
        dest='filename',
        action='store',
        required=False,
        default='addresses.yaml',
        help='specifies the name of the file containing the addresses',
    )

    parser.add_argument(
        '-n', '--network',
        dest='network',
        action='store',
        required=True,
        default='all',
        help='specifies the name of the network to use (all/polygon/sepolia)',
    )

    parser.add_argument(
        '-c', '--contracts',
        dest='doContracts',
        action='store_true',
        required=False,
        default=False,
        help='specifies whether to start from contracts (or from wallet addresses)',
    )
    args, unknown = parser.parse_known_args()

    if len(unknown) > 0:
        print(f'Unknown options {unknown}')
        parser.print_help()
        exit(-1)

    if args.network not in ['polygon', 'sepolia', 'all']:
        print(f'Network not supported: {args.network}')
        parser.print_help()
        exit(-1)

    calculate_metrics(filename=args.filename, doContracts=args.doContracts, network=args.network)
