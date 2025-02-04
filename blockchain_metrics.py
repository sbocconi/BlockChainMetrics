from utils import read_yaml, Int2HexStr, HexStr2Int
from polygonscan import PolygonScan
from addresstransactions import AddressTransactions


SETTINGS_FILE = '.settings.yaml'
WEI_TO_POL = 10**18

def main(filename, doContracts, network):
    settings = read_yaml(SETTINGS_FILE)
    token = settings[f'{network}']['token']
    calls_sec = settings[f'{network}']['calls_sec']
    endpoint = settings[f'{network}']['endpoint']
    
    ps = PolygonScan(endpoint, token, calls_sec)
    
    addresses = read_yaml(filename)
    
    wallets = None
    contracts = None
    
    if doContracts:
        contracts = addresses['contracts']
    else:
        wallets = addresses['wallets']
    # breakpoint()
    
    if wallets == None:
        wallets = ps.get_wallets(contracts)
    
    # breakpoint()
    balances = ps.get_POL_balance(wallets)
    for balance in balances:
        print(f"Account {balance['account']} has {balance['balance']} wei, {int(balance['balance'])/WEI_TO_POL} POL")
    
    total_metrics = []
    for wallet in wallets:
        print(f'######## Address {wallet} ########')

        addr_metrics = AddressTransactions(wallet, ps)
        
        if not addr_metrics.get_transactions():
            continue
        
        addr_metrics.set_ERC1155_transfers()

        addr_metrics.set_ERC721_transfers()
        
        total_metrics.append(addr_metrics)
        
        # breakpoint()
        # transfers = ps.get_ERC20_token_transfers(address=wallet,contract_address=None)
        # if transfers is not None:
        #     print(f'{len(transfers)} ERC20 token transfers')
        #     for transfer in transfers:
        #         print(transfer)
        
        # transactions = ps.get_normal_transactions(address=wallet)
        # print(f'{len(transactions)} Normal transactions')
        # for transaction in transactions:
        #     print(transaction)

        # transactions = ps.get_internal_transactions(address=wallet)
        # print(f'{len(transactions)} Internal transactions')
        # for transaction in transactions:
        #     print(transaction)

        # balance = ps.get_ERC20_token_balance(address=wallet,contract_address=contract_address)
        # print(f'ERC-20 Token Account Balance: {balance}')
        
        # supply = ps.get_ERC20_token_supply(contract_address=contract_address)
        # print(f'ERC-20 Token TotalSupply: {supply} for contractAddress {contract_address}')
    
    # for addr_metrics in total_metrics:
    #     for nft in addr_metrics.NFTs:
    #         for i in range(len(nft.statuses)):
    #             if len(nft.contractAddresses) != len(nft.statuses):
    #                 breakpoint()
    #             print(f'{Int2HexStr(nft.contractAddresses[i])}, {nft.statuses[i]}')

    total_gov_nfts = 0
    total_bought_nfts = 0
    total_sold_nfts = 0
    total_gains = 0
    total_costs = 0
    total_addrs = len(total_metrics)

    for addr_metrics in total_metrics:
        addr_gov_nfts = 0
        addr_bought_nfts = 0
        addr_sold_nfts = 0
        addr_gains = 0
        addr_costs = 0
        for nft in addr_metrics.NFTs:
            if nft.is_gov():
                addr_gov_nfts = addr_gov_nfts + 1
                continue
            if nft.was_ever_sold():
                addr_sold_nfts = addr_sold_nfts + 1
                addr_gains = addr_gains + nft.get_revenue()
            if nft.was_ever_bought():
                addr_bought_nfts = addr_bought_nfts + 1
                addr_costs = addr_costs + nft.get_costs()
            if not (nft.is_gov() or nft.was_ever_sold() or nft.was_ever_bought() or nft.was_ever_created()):
                raise Exception(f'NFT {nft.id} has no known status')
            
        total_gov_nfts = total_gov_nfts + addr_gov_nfts
        total_bought_nfts = total_bought_nfts + addr_bought_nfts
        total_sold_nfts = total_sold_nfts + addr_sold_nfts
        total_gains = total_gains + addr_gains
        total_costs = total_costs + addr_costs

    print(f'Total addresses: {total_addrs}')
    print(f'Average governance NFTs: {total_gov_nfts}/{total_addrs} = {total_gov_nfts/total_addrs}')
    print(f'Average bought NFTs: {total_bought_nfts}/{total_addrs} = {total_bought_nfts/total_addrs}')
    print(f'Average sold NFTs: {total_sold_nfts}/{total_addrs} = {total_sold_nfts/total_addrs}')
    print(f'Average gains from sold NFTs (POL): {total_gains/WEI_TO_POL}/{total_addrs} = {total_gains/WEI_TO_POL/total_addrs}')
    print(f'Average costs from buying NFTs (POL): {total_costs/WEI_TO_POL}/{total_addrs} = {total_costs/WEI_TO_POL/total_addrs}')

    # breakpoint()


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
        required=False,
        default='polygon',
        help='specifies the name of the network to use (polygon/sepolia)',
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

    if args.network not in ['polygon', 'sepolia']:
        print(f'Network not supported: {args.network}')
        parser.print_help()
        exit(-1)

    main(filename=args.filename, doContracts=args.doContracts, network=args.network)
