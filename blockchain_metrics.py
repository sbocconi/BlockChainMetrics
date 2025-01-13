import yaml
from pathlib import Path
import requests
import time
from datetime import datetime


SETTINGS_FILE = '.settings.yaml'
WEI_TO_POL = 10**18

TRANS_CACHE = {}

def read_yaml(filename):
    full_file_path = Path(__file__).parent.joinpath(filename)
    with open(full_file_path) as settings:
        settings = yaml.load(settings, Loader=yaml.Loader)
    return settings

def print_error(error):
    print('ERROR!!')
    print(error)
    print("\n")

def HexStr2Int(hexstring:str) -> int:
    if hexstring.lower() == '0x':
        return 0
    if hexstring == '':
        return None
    return int(hexstring,16)

def Int2HexStr(numint:int) -> str:
    """
        Convert to hex with padding to get even length
    """
    enc_ln = len(hex(numint)) - len('0x')
    padd = enc_ln + enc_ln % 2
    # breakpoint()
    return f'0x{numint:0{padd}x}'

class PolygonScan:
    
    def __init__(self, endpoint, token, calls_sec):
        # Parameters for http calls
        self.endpoint = endpoint
        self.token = token
        
        # Parameters for call throttling
        self.calls_sec = calls_sec
        self.count = 0
        
        # Initialise time stamps
        self.time_stamps = [0 for i in range(calls_sec+1)]

    def throttle(self):
        """
            Limit the amount of calls per second to self.calls_sec
        """
        self.time_stamps[self.count] = time.time_ns() // 1_000_000
        
        # Index of timestamp for calls_sec ago
        wnd_start = (self.count + 1) % (self.calls_sec+1)

        # if we have not made self.calls_sec yet, do not throttle
        if not self.time_stamps[wnd_start] == 0:
            # 1 sec less the time we took to make self.calls_sec calls
            sleep_ms = 1000 - (self.time_stamps[self.count] - self.time_stamps[wnd_start])

            if sleep_ms > 1000:
                # This means we screwed the calculation
                # as later call cannot be earlier than previous calls
                raise Exception(f'sleep is {sleep_ms}')
            
            if sleep_ms > 0:
                # We need to wait
                print(f'Sleeping {sleep_ms} ms')
                time.sleep(sleep_ms/1000)
                # Update time of action since we slept
                self.time_stamps[self.count] = time.time_ns() // 1_000_000

        # print(f'self.count {self.count}, wnd_start {wnd_start}, self.time_stamps {self.time_stamps}')
        
        # Update the index for the next call
        self.count = wnd_start

    
    def make_call(self, api_url, paginated=False, attempt=0):
        """
            Generic wrapper for HTTP calls
        """
        if attempt > 5:
            raise Exception(f'{api_url} timed out ({attempt} times)')
        
        result = None
        results = []
        page = 1
        offset = 100
        startblock=0
        endblock=99999999
        while True:
            if paginated:
                # We are making a call to a paginated endpoint
                api_url_page = f'{api_url}&page={page}&offset={offset}&startblock={startblock}&endblock={endblock}'
            else:
                api_url_page = api_url
            try:
                self.throttle()
                response = requests.get(api_url_page)
                if response.status_code == 200:
                    payload = response.json()
                    if 'message' in payload and payload['message'] != 'OK' and payload['message'] != 'No transactions found':
                        print_error(f'Url {api_url_page} gave response {payload}')
                        # breakpoint()
                        return None
                    if 'result' in payload:
                        result = payload['result']
                    else:
                        breakpoint()
                else:
                    print_error(f'Url {api_url_page} gave response {response.status_code}, {response}')
                    return None
            except requests.Timeout:
                # We retry increasing the attempt number
                print(f'Retrying call {api_url_page}, attempt {attempt+1}')
                return self.make_call(api_url=api_url_page, attempt=attempt+1)
            except requests.exceptions.RequestException as e:
                # This should catch all other requests exceptions
                raise(f'Got {e} while calling {api_url_page}')
            if not paginated:
                return result
            elif paginated and result == []:
                return results
            else:
                if result == None:
                    # Should not happen
                    raise(f'Result is None while calling {api_url_page}')
                results.extend(result)
                if len(result) < offset:
                    return results
                else:
                    # We continue paginating
                    page = page + 1
                    # print(f'Paginating call {api_url_page}, page {page}')
                # breakpoint()

        

    def get_POL_balance(self, addresses:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-a-single-address
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-multiple-addresses-in-a-single-call
        """
        balances = None
        module = 'account'
        tag = 'latest'
        
        if type(addresses) == list:
            action = 'balancemulti'
            addr_list = ','.join([Int2HexStr(address) for address in addresses])
            api_url = f'{self.endpoint}?module={module}&action={action}&address={addr_list}&tag={tag}&apikey={self.token}'
        else:
            action = 'balance'
            api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(addresses)}&tag={tag}&apikey={self.token}'

        result = self.make_call(api_url)

        if result != None:
            if type(result) == list:
                balances = result
            else:
                balances = [{'account': addresses, 'balance': f'{result}'}]
            # breakpoint()
        return balances

    def get_transaction_count(self, address:int):
        """
           https://docs.polygonscan.com/api-endpoints/geth-parity-proxy#eth_gettransactioncount
        """
        module = 'proxy'
        action = 'eth_getTransactionCount'
        tag = 'latest'
    
        api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(address)}&tag={tag}&apikey={self.token}'
        result = self.make_call(api_url=api_url, paginated=False)

        return result

    def get_transaction(self, txhash):
        """
           https://docs.polygonscan.com/api-endpoints/geth-parity-proxy#eth_gettransactionbyhash 
        """
        module = 'proxy'
        action = 'eth_getTransactionByHash'
    
        api_url = f'{self.endpoint}?module={module}&action={action}&txhash={Int2HexStr(txhash)}&apikey={self.token}'
        result = self.make_call(api_url=api_url, paginated=False)

        return result

    def get_normal_transactions(self, address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-normal-transactions-by-address
        """
        module = 'account'
        action = 'txlist'
        sort = 'asc'
        startblock = 0
        endblock = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(address)}&sort={sort}&startblock={startblock}&endblock={endblock}&apikey={self.token}'

        results = self.make_call(api_url=api_url, paginated=True)

        return results

    def get_internal_transactions(self, address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-internal-transactions-by-address
        """
        module = 'account'
        action = 'txlistinternal'
        sort = 'asc'
        startblock = 0
        endblock = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(address)}&sort={sort}&startblock={startblock}&endblock={endblock}&apikey={self.token}'

        results = self.make_call(api_url=api_url, paginated=True)

        return results

    def get_ERC_token_transfers(self, action:str, address:int, contract_address:int):
        module = 'account'
        action = action
        sort = 'asc'
        api_url = f'{self.endpoint}?module={module}&action={action}&sort={sort}&apikey={self.token}'
        
        if address is None and contract_address is None:
            raise Exception(f'Address and contract address cannot be both null')

        if address is not None:
            api_url = f'{api_url}&address={Int2HexStr(address)}'
        if contract_address is not None:
            api_url = f'{api_url}&contractaddress={Int2HexStr(contract_address)}'
        
        results = self.make_call(api_url=api_url,  paginated=True)

        return results
    
    def get_ERC20_token_transfers(self, address:int, contract_address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-erc-20-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'tokentx', address=address, contract_address=contract_address)

    def get_ERC721_token_transfers(self, address:int, contract_address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-erc-721-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'tokennfttx', address=address, contract_address=contract_address)

    def get_ERC1155_token_transfers(self, address:int, contract_address:int):
        """
            https://docs.polygonscan.com/api-endpoints/accounts#get-a-list-of-erc1155-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'token1155tx', address=address, contract_address=contract_address)

    def get_ERC20_token_supply(self, contract_address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/tokens#get-erc-20-token-totalsupply-by-contractaddress
        """
        module = 'stats'
        action = 'tokensupply'
        api_url = f'{self.endpoint}?module={module}&action={action}&contractaddress={Int2HexStr(contract_address)}&apikey={self.token}'
        result = self.make_call(api_url)
        return result

    def get_ERC20_token_balance(self, address:int, contract_address:int):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/tokens#get-erc-20-token-account-balance-by-contractaddress
        """
        module = 'account'
        action = 'tokenbalance'
        tag = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(address)}&contractaddress={Int2HexStr(contract_address)}&tag={tag}&apikey={self.token}'
        result = self.make_call(api_url)
        return result

class NFT:
    GOV_NFT = 'NftGovernance'
    GOV_CONTRACT = '0x88e0f9b16f5c3ff1f48576bf2dc785070c6a86a5'
    NFT_CREATION_ADR = HexStr2Int('0x0000000000000000000000000000000000000000')
    CREATED = 'created'
    SOLD = 'sold'
    BOUGHT = 'bought'
    GOV = 'governance'

    def __init__(self, nft_tokenID):
        self.id = nft_tokenID
        self.dates = []
        self.froms = []
        self.tos = []
        self.contractAddresses = []
        self.tokenValues = []
        self.tokenNames = []
        self.values = []
        self.statuses = []
        self.txhashes = []
        
    def update_nft(self, user_addr:int, nft_date:datetime, nft_from:int, nft_to:int, nft_contractAddress:int, nft_tokenValue:int, nft_tokenName:str, transaction:dict):
        self.dates.append(nft_date)
        self.froms.append(nft_from)
        self.tos.append(nft_to)
        self.contractAddresses.append(nft_contractAddress)
        self.tokenValues.append(nft_tokenValue)
        self.tokenNames.append(nft_tokenName)
        self.txhashes.append(transaction['hash'])

        if type(transaction['value']) == int:
            nft_value = transaction['value']
        elif transaction['value'].lower().startswith('0x'):
            nft_value = HexStr2Int(transaction['value'])
        else:
            raise Exception(f"Unknown format for value: {transaction['value']}")
        self.values.append(nft_value)
        # breakpoint()

        try:
            if user_addr == self.froms[-1]:
                # This NFT was sold
                # breakpoint()
                self.set_sold()

            elif user_addr == self.tos[-1]:
                if self.froms[-1] == NFT.NFT_CREATION_ADR:
                    # This NFT was created
                    # breakpoint()
                    self.set_created()
                    if self.tokenNames[-1] == NFT.GOV_NFT:
                        # breakpoint()
                        self.set_gov()
                else:
                    # This NFT was bought
                    # breakpoint()
                    self.set_bought()
            else:
                raise Exception(f'Address {user_addr} is not in to or from for nft {self.id}')
        except Exception as e:
            print_error(e)
            print(f'List of transactions: {[Int2HexStr(i) for i in self.txhashes]}')
            breakpoint()

    def set_created(self):
        if len(self.statuses) != 0:
            raise Exception(f'NFT {self.id} has incompatible status to be created')

        if self.values[-1] != 0:
            raise Exception(f'NFT {self.id} is created but there is money involved')

        self.statuses.append(NFT.CREATED)

    def set_sold(self):
        if (len(self.statuses) == 0) or self.is_gov():
            raise Exception(f'NFT {self.id} has incompatible status to be sold')
        if self.values[-1] == 0:
            raise Exception(f'NFT {self.id} is sold but for no money')
        self.statuses.append(NFT.SOLD)

    def set_bought(self):
        if self.is_gov():
            raise Exception(f'NFT {self.id} has incompatible status to be bought')
        if self.values[-1] == 0:
            raise Exception(f'NFT {self.id} is bought but for no money')
        self.statuses.append(NFT.BOUGHT)

    def set_gov(self):
        if self.was_ever_sold() or self.was_ever_bought():
            raise Exception(f'NFT {self.id} has incompatible status to be a governance NFT')
        self.statuses.append(NFT.GOV)

    def was_ever_sold(self) -> bool:
        for i in range(len(self.statuses)):
            if self.statuses[i] == NFT.SOLD:
                return True
        return False

    def was_ever_bought(self) -> bool:
        for i in range(len(self.statuses)):
            if self.statuses[i] == NFT.BOUGHT:
                return True
        return False
    
    def was_ever_created(self) -> bool:
        if len(self.statuses) == 0:
            return False
        # Creation can only be the first transaction
        for i in range(1,len(self.statuses)):
            if self.statuses[i] == NFT.CREATED:
                raise Exception(f'NFT {self.id} has creation at trans {i} > 0')
        if not self.statuses[0] == NFT.CREATED:
            return False
        return True
    
    def is_gov(self) -> bool:
        for i in range(len(self.statuses)):
            if self.statuses[i] == NFT.GOV:
                return True
        return False

    def get_revenue(self) -> int:
        rev = 0
        for i in range(len(self.statuses)):
            if self.statuses[i] == NFT.SOLD:
                rev = rev + self.values[i]
        return rev
    
    def get_costs(self) -> int:
        cst = 0
        for i in range(len(self.statuses)):
            if self.statuses[i] == NFT.BOUGHT:
                cst = cst + self.values[i]
        return cst



class AddressMetrics:

    def __init__(self, address:str, ps:PolygonScan):
        self.address = address
        self.ps = ps
        
        self.NFTs = []

    def get_transactions(self, address:str=None):
        if address == None:
            target_addr = self.address
        else:
            target_addr = address
        transactions = self.ps.get_normal_transactions(address=target_addr)
        if transactions == None:
            print(f'No  transactions for {Int2HexStr(target_addr)}')
            return False
        print(f'{len(transactions)} Normal transactions for {Int2HexStr(target_addr)}')
        for tr in transactions:
            # print(tr)
            txhash = HexStr2Int(tr['hash'])
            if Int2HexStr(txhash) not in TRANS_CACHE:
                TRANS_CACHE[Int2HexStr(txhash)] = {}
                TRANS_CACHE[Int2HexStr(txhash)]['date'] = datetime.fromtimestamp(int(tr['timeStamp']))
                TRANS_CACHE[Int2HexStr(txhash)]['hash'] = txhash
                TRANS_CACHE[Int2HexStr(txhash)]['from'] = HexStr2Int(tr['from'])
                TRANS_CACHE[Int2HexStr(txhash)]['to'] = HexStr2Int(tr['to'])
                TRANS_CACHE[Int2HexStr(txhash)]['value'] = int(tr['value'])
                TRANS_CACHE[Int2HexStr(txhash)]['methodId'] = HexStr2Int(tr['methodId'])
        return True
    
    def parse_token_transfers(self, transfers, tokentype):
        for tr in transfers:
            # print(tr)
            tokenID = int(tr['tokenID'])
            tr_date = datetime.fromtimestamp(int(tr['timeStamp']))
            tr_from = HexStr2Int(tr['from'])
            tr_to = HexStr2Int(tr['to'])
            contractAddress = HexStr2Int(tr['contractAddress'])
            if tokentype == 'ERC1155':
                tokenValue = int(tr['tokenValue'])
            elif tokentype == 'ERC721':
                tokenValue = 1
            else:
                raise Exception(f'Token type {tokentype} not supported!')
            
            tokenName = tr['tokenName']
            txhash = HexStr2Int(tr['hash'])
            transaction = self.retrieve_transaction(txhash)
            if transaction == None:
                print(f'Transaction hash {Int2HexStr(txhash)} not found, retrieving more transactions')
                if tr_from == NFT.NFT_CREATION_ADR or tr_to == NFT.NFT_CREATION_ADR:
                    # Too many transactions and they should be all of type mint with no costs
                    transaction = self.ps.get_transaction(txhash)
                else:
                    # Non minting transactions don't seem to contain the price of the NFT,
                    # thus we proceed by retrieving the transactions of the other party
                    if self.address == tr_from:
                        self.get_transactions(address=tr_to)
                    else:
                        self.get_transactions(address=tr_from)
                    transaction = self.retrieve_transaction(txhash)
            if transaction == None:
                breakpoint()
                raise Exception(f'Transaction hash {Int2HexStr(txhash)} not found')
            
            # breakpoint()
            nft = self.retrieve_nft(tokenID)
            nft.update_nft(self.address, tr_date, tr_from, tr_to, contractAddress, tokenValue, tokenName, transaction)
        return True

    def set_ERC1155_transfers(self):
        transfers = self.ps.get_ERC1155_token_transfers(address=self.address, contract_address=None)
        if transfers == None:
            print(f'No ERC1155 token transfers for {Int2HexStr(self.address)}')
            return False
        print(f'{len(transfers)} ERC1155 token transfers for {Int2HexStr(self.address)}')
        return self.parse_token_transfers(transfers, 'ERC1155')

    def set_ERC721_transfers(self):
        transfers = self.ps.get_ERC721_token_transfers(address=self.address, contract_address=None)
        if transfers == None:
            print(f'No ERC721 token transfers for {Int2HexStr(self.address)}')
            return False
        print(f'{len(transfers)} ERC721 token transfers for {Int2HexStr(self.address)}')
        return self.parse_token_transfers(transfers, 'ERC721')

    def retrieve_nft(self, id):
        for nft in self.NFTs:
            if nft.id == id:
                return nft
        nft = NFT(id)
        self.NFTs.append(nft)
        return nft

    def retrieve_transaction(self, txhash):
        if Int2HexStr(txhash) in TRANS_CACHE:
            return TRANS_CACHE[Int2HexStr(txhash)]
        return None
        # print(f'Transaction hash {txhash} not found')
        # return None


def main(filename):
    settings = read_yaml(SETTINGS_FILE)
    token = settings['polygon']['token']
    calls_sec = settings['polygon']['calls_sec']
    endpoint = settings['polygon']['endpoint']
    
    ps = PolygonScan(endpoint, token, calls_sec)
    
    addresses = read_yaml(filename)
    wallets = addresses['wallets']
    # breakpoint()
    
    balances = ps.get_POL_balance(wallets)
    for balance in balances:
        print(f"Account {balance['account']} has {balance['balance']} wei, {int(balance['balance'])/WEI_TO_POL} POL")
    
    total_metrics = []
    for wallet in wallets:
        print(f'######## Address {wallet} ########')

        addr_metrics = AddressMetrics(wallet, ps)
        
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
    print(f'Average governance NFTs: {total_gov_nfts/total_addrs}')
    print(f'Average bought NFTs: {total_bought_nfts/total_addrs}')
    print(f'Average sold NFTs: {total_sold_nfts/total_addrs}')
    print(f'Average gains from sold NFTs: {total_gains/total_addrs/WEI_TO_POL}')
    print(f'Average costs from buying NFTs: {total_costs/total_addrs/WEI_TO_POL}')

    breakpoint()


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
    args, unknown = parser.parse_known_args()

    if len(unknown) > 0:
        print(f'Unknown options {unknown}')
        parser.print_help()
        exit(-1)

    main(args.filename)
