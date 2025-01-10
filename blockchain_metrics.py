import yaml
from pathlib import Path
import requests
import time
from datetime import datetime


SETTINGS_FILE = '.settings.yaml'
WEI_TO_POL = 10**18

def read_yaml(filename):
    full_file_path = Path(__file__).parent.joinpath(filename)
    with open(full_file_path) as settings:
        settings = yaml.load(settings, Loader=yaml.Loader)
    return settings

def print_error(error):
    print('\nERROR!!')
    print(error)
    print("\n")


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
                    if payload['message'] != 'OK' and payload['message'] != 'No transactions found':
                        print_error(f'Url {api_url_page} gave response {payload}')
                        # breakpoint()
                        return None
                    result = payload['result']
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
                    # Should not happen, see why
                    breakpoint()
                results.extend(result)
                if len(result) < offset:
                    return results
                else:
                    # We continue paginating
                    page = page + 1
                    # print(f'Paginating call {api_url_page}, page {page}')
                # breakpoint()

        

    def get_POL_balance(self, addresses):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-a-single-address
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-multiple-addresses-in-a-single-call
        """
        balances = None
        module = 'account'
        tag = 'latest'
        
        if type(addresses) == list:
            action = 'balancemulti'
            addr_list = ','.join(addresses)
            api_url = f'{self.endpoint}?module={module}&action={action}&address={addr_list}&tag={tag}&apikey={self.token}'
        else:
            action = 'balance'
            api_url = f'{self.endpoint}?module={module}&action={action}&address={addresses}&tag={tag}&apikey={self.token}'

        result = self.make_call(api_url)

        if result != None:
            if type(result) == list:
                balances = result
            else:
                balances = [{'account': addresses, 'balance': f'{result}'}]
            # breakpoint()
        return balances


    def get_normal_transactions(self, address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-normal-transactions-by-address
        """
        module = 'account'
        action = 'txlist'
        sort = 'asc'
        startblock = 0
        endblock = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={address}&sort={sort}&startblock={startblock}&endblock={endblock}&apikey={self.token}'

        results = self.make_call(api_url=api_url, paginated=True)

        return results

    def get_internal_transactions(self, address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-internal-transactions-by-address
        """
        module = 'account'
        action = 'txlistinternal'
        sort = 'asc'
        startblock = 0
        endblock = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={address}&sort={sort}&startblock={startblock}&endblock={endblock}&apikey={self.token}'

        results = self.make_call(api_url=api_url, paginated=True)

        return results

    def get_ERC_token_transfers(self, action, address, contract_address):
        module = 'account'
        action = action
        sort = 'asc'
        api_url = f'{self.endpoint}?module={module}&action={action}&sort={sort}&apikey={self.token}'
        if address is not None and contract_address is None:
            api_url = f'{api_url}&address={address}'
        elif address is None and contract_address is not None:
            api_url = f'{api_url}&contractaddress={contract_address}'
        elif address is not None and contract_address is not None:
            api_url = f'{api_url}&address={address}&contractaddress={contract_address}'
        else:
            raise Exception(f'Address and contract address cannot be both null')
        

        results = self.make_call(api_url=api_url,  paginated=True)

        return results
    
    def get_ERC20_token_transfers(self, address, contract_address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-erc-20-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'tokentx', address=address, contract_address=contract_address)

    def get_ERC721_token_transfers(self, address, contract_address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-a-list-of-erc-721-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'tokennfttx', address=address, contract_address=contract_address)

    def get_ERC1155_token_transfers(self, address, contract_address):
        """
            https://docs.polygonscan.com/api-endpoints/accounts#get-a-list-of-erc1155-token-transfer-events-by-address
        """
        return self.get_ERC_token_transfers(action = 'token1155tx', address=address, contract_address=contract_address)

    def get_ERC20_token_supply(self, contract_address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/tokens#get-erc-20-token-totalsupply-by-contractaddress
        """
        module = 'stats'
        action = 'tokensupply'
        api_url = f'{self.endpoint}?module={module}&action={action}&contractaddress={contract_address}&apikey={self.token}'
        result = self.make_call(api_url)
        return result

    def get_ERC20_token_balance(self, address, contract_address):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/tokens#get-erc-20-token-account-balance-by-contractaddress
        """
        module = 'account'
        action = 'tokenbalance'
        tag = 'latest'
        api_url = f'{self.endpoint}?module={module}&action={action}&address={address}&contractaddress={contract_address}&tag={tag}&apikey={self.token}'
        result = self.make_call(api_url)
        return result

class NFT:
    GOV_NFT = 'NftGovernance'
    GOV_CONTRACT = '0x88e0f9b16f5c3ff1f48576bf2dc785070c6a86a5'
    NFT_CREATION_ADR = '0x0000000000000000000000000000000000000000'

    def __init__(self, nft_tokenID):
        self.id = nft_tokenID
        self.nft_dates = []
        self.nft_froms = []
        self.nft_tos = []
        self.nft_contractAddresses = []
        self.nft_tokenValues = []
        self.nft_tokenNames = []
        self.sold = [False]
        self.created = [False]
        self.bought = [False]
        self.governance = [False]
        self.nr_trans = -1
        
    def update_nft(self, user_addr, nft_date, nft_from, nft_to, nft_contractAddress, nft_tokenValue, nft_tokenName):
        self.nr_trans = self.nr_trans + 1
        self.nft_dates.append(nft_date)
        self.nft_froms.append(nft_from)
        self.nft_tos.append(nft_to)
        self.nft_contractAddresses.append(nft_contractAddress)
        self.nft_tokenValues.append(nft_tokenValue)
        self.nft_tokenNames.append(nft_tokenName)

        if user_addr == self.nft_froms[self.nr_trans]:
            # This NFT was sold
            self.set_sold()

        elif user_addr == self.nft_tos[self.nr_trans]:
            if self.nft_froms[self.nr_trans] == NFT.NFT_CREATION_ADR:
                # This NFT was created
                self.set_created()
                if self.nft_tokenNames[self.nr_trans] == NFT.GOV_NFT:
                    self.set_gov()
            else:
                # This NFT was bought
                self.set_bought()
        else:
            raise Exception(f'Address {user_addr} is not in to or from for nft {self.id}')

    def set_created(self):
        if self.nr_trans != 0:
            raise Exception(f'NFT {self.id} cannot be created when a transaction already exists')
        
        if self.sold[self.nr_trans] or self.bought[self.nr_trans] or self.governance[self.nr_trans]:
            raise Exception(f'NFT {self.id} has incompatible status to be created')
        self.created.append(True)

    def set_sold(self):
        if (self.nr_trans == 0) or self.is_gov():
            raise Exception(f'NFT {self.id} has incompatible status to be sold')
        self.sold.append(True)

    def set_bought(self):
        if self.is_gov():
            raise Exception(f'NFT {self.id} has incompatible status to be bought')
        self.bought = True

    def set_gov(self):
        if self.was_ever_sold() or self.was_ever_bought():
            raise Exception(f'NFT {self.id} has incompatible status to be a governance NFT')
        self.governance = True

    def was_ever_sold(self):
        for i in range(self.nr_trans):
            if self.sold[i] == True:
                return True
        return False

    def was_ever_bought(self):
        for i in range(self.nr_trans):
            if self.bought[i] == True:
                return True
        return False
    
    def was_ever_created(self):
        for i in range(1,self.nr_trans):
            if self.created[i] == True:
                raise Exception(f'NFT {self.id} has creation at trans {i} > 0')
        if not self.created[0] == True:
            return False
        return True
        
    
    def is_gov(self):
        for i in range(self.nr_trans):
            if self.governance[i] == True:
                return True
        return False



class AddressMetrics:
    MADE_IDX = 0
    SOLD_IDX = 1
    BOUGHT_IDX = 2


    def __init__(self, address):
        self.address = address
        self.NFTs = []
        
        self.NFT_made = 0
        self.NFT_sold = 0
        self.NFT_bought = 0


    def ERC1155_metrics(self, transfers:list):
        if transfers == None:
            print(f'No ERC1155 token transfers for {self.address}')
            return
        print(f'{len(transfers)} ERC1155 token transfers for {self.address}')
        for tr in transfers:
            print(tr)
            tokenID = int(tr['tokenID'])
            if tokenID == 127 or tokenID == 16 or tokenID == 20:
                continue
            nft = self.retrieve_nft(tokenID)
            tr_date = datetime.fromtimestamp(int(tr['timeStamp']))
            tr_from = tr['from']
            tr_to = tr['to']
            contractAddress = tr['contractAddress']
            tokenValue = tr['tokenValue']
            tokenName = tr['tokenName']

            nft.update_nft(self.address, tr_date, tr_from, tr_to, contractAddress, tokenValue, tokenName)

    def retrieve_nft(self, id):
        for nft in self.NFTs:
            if nft.id == id:
                return nft
        nft = NFT(id)
        self.NFTs.append(nft)
        return nft


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
        
    for wallet in wallets:
        print(f'######## Address {wallet} ########')
        
        transfers = ps.get_ERC1155_token_transfers(address=wallet, contract_address=None)
        metrics = AddressMetrics(wallet)
        metrics.ERC1155_metrics(transfers)
        
        breakpoint()
        

        transfers = ps.get_ERC20_token_transfers(address=wallet,contract_address=None)
        if transfers is not None:
            print(f'{len(transfers)} ERC20 token transfers')
            for transfer in transfers:
                print(transfer)

        transfers = ps.get_ERC721_token_transfers(address=wallet,contract_address=None)
        if transfers is not None:
            print(f'{len(transfers)} ERC721 token transfers')
            for transfer in transfers:
                print(transfer)

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
