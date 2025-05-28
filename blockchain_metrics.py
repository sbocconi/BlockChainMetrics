from .utils import read_yaml, Int2HexStr, HexStr2Int, make_percentage
from .blockchainscan import BlockChainScan
from .addresstransactions import AddressTransactions


SETTINGS_FILE = '.settings.yaml'
WEI_TO_POL = 10**18

def create_scanner(network):
    settings = read_yaml(SETTINGS_FILE)

    token = settings[f'{network}']['token']
    calls_sec = settings[f'{network}']['calls_sec']
    endpoint = settings[f'{network}']['endpoint']

    bs = BlockChainScan(network, endpoint, token, calls_sec)
    return bs


def metrics_per_wallet(wallets, bs):
    total_metrics = []
    for wallet in wallets:
            print(f'######## Address {Int2HexStr(wallet)} ########')

            addr_metrics = AddressTransactions(wallet, bs)
            
            if not addr_metrics.get_transactions():
                continue
            
            addr_metrics.set_ERC1155_transfers()

            addr_metrics.set_ERC721_transfers()
            
            total_metrics.append(addr_metrics)
    
    return total_metrics
            

def calculate_metrics(filename, doContracts, network, wallets:list[int]=None):
    if network == 'all':
        networks = ['sepolia', 'polygon']
    else:
        networks = [network]
    
    if doContracts:
        addresses = read_yaml(filename)
        contracts = addresses['contracts']
        wallets = None
    else:
        contracts = None
        if wallets == None:
            addresses = read_yaml(filename)
            wallets = addresses['wallets']
        
    # breakpoint()
        
    total_metrics = []
    for network in networks:
        print(f'Running on network: {network}')
    
        bs = create_scanner(network)
        
        if wallets == None:
            wallets = bs.get_wallets(contracts)
        
        # breakpoint()

        balances = bs.get_POL_balance(wallets)
        for balance in balances:
            print(f"Account {balance['account']} has {balance['balance']} wei, {int(balance['balance'])/WEI_TO_POL} POL")
        
        total_metrics.extend(metrics_per_wallet(wallets, bs))
        # breakpoint()

        
    # breakpoint()
    total_gov_nfts = 0
    total_bought_nfts = 0
    total_sold_nfts = 0
    total_gains = 0
    total_costs = 0
    total_addrs = len(wallets)
    total_sellers = []
    total_buyers = []

    for addr_metrics in total_metrics:
        # We use variables internal to the loop in case we want to
        # perform some per wallet statistics, not for the moment
        addr_gov_nfts = 0
        addr_bought_nfts = 0
        addr_sold_nfts = 0
        addr_gains = 0
        addr_costs = 0
        sellers = []
        buyers = []

        for nft in addr_metrics.NFTs:
            if nft.is_gov():
                addr_gov_nfts = addr_gov_nfts + 1
                # breakpoint()
                continue
            if nft.was_ever_sold():
                # breakpoint()
                addr_sold_nfts = addr_sold_nfts + nft.get_nr_sales()
                addr_gains = addr_gains + nft.get_revenue()
                sellers.extend(nft.get_sellers())
            if nft.was_ever_bought():
                addr_bought_nfts = addr_bought_nfts + nft.get_nr_purchases()
                addr_costs = addr_costs + nft.get_costs()
                buyers.extend(nft.get_buyers())
            if not (nft.is_gov() or nft.was_ever_sold() or nft.was_ever_bought() or nft.was_ever_created()):
                raise Exception(f'NFT {nft.id} has no known status')
            
        total_gov_nfts += addr_gov_nfts
        total_bought_nfts += addr_bought_nfts
        total_sold_nfts += addr_sold_nfts
        total_gains += addr_gains
        total_costs += addr_costs
        total_sellers.extend(sellers)
        total_buyers.extend(buyers)

    # breakpoint()
    total_sellers_nr = len(set(total_sellers))
    total_buyers_nr = len(set(total_buyers))
    print(f'Total wallets: {total_addrs}')
    print(f'Number of sales+purchases: {total_bought_nfts+total_sold_nfts}')
    print(f'Average governance NFTs: {total_gov_nfts}/{total_addrs} = {total_gov_nfts/total_addrs}')
    print(f'Average times NFTs are bought: {total_bought_nfts}/{total_addrs} = {total_bought_nfts/total_addrs}')
    print(f'Average times NFTs are sold: {total_sold_nfts}/{total_addrs} = {total_sold_nfts/total_addrs}')
    print(f'Percentage sellers with at least one sale: {total_sellers_nr}/{total_addrs} = {make_percentage(total_sellers_nr/total_addrs)}%')
    print(f'Percentage buyers with at least one purchase: {total_buyers_nr}/{total_addrs} = {make_percentage(total_buyers_nr/total_addrs)}%')
    print(f'Sold NFTs: average revenues per wallet (POL): {total_gains/WEI_TO_POL}/{total_addrs} = {total_gains/WEI_TO_POL/total_addrs}')
    print(f'Sold NFTs: average revenues per NFT (POL): {total_gains/WEI_TO_POL}/{total_sold_nfts} = {total_gains/WEI_TO_POL/total_sold_nfts}')
    print(f'Bought NFTs: average price per wallet (POL): {total_costs/WEI_TO_POL}/{total_addrs} = {total_costs/WEI_TO_POL/total_addrs}')
    print(f'Bought NFTs: average price per NFT(POL): {total_costs/WEI_TO_POL}/{total_bought_nfts} = {total_costs/WEI_TO_POL/total_bought_nfts}')

    # breakpoint()