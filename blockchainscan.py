import requests
import time

from .utils import Int2HexStr, HexStr2Int, print_error

# SEP_MAX_RATE = 'Max calls per sec rate limit reached (5/sec)'
SEP_MAX_RATE_MSG = 'Max calls'
POL_MAX_RATE_MSG = 'Max rate'

class BlockChainScan:
    SAFETY = 50

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
                time.sleep((sleep_ms+self.SAFETY)/1000)
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
        
        throttled = False
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
                # print(api_url_page)
                response = requests.get(api_url_page)
                if response.status_code == 200:
                    payload = response.json()
                    if 'message' in payload and payload['message'] != 'OK':
                        # breakpoint()
                        if payload['message'] == 'No transactions found':
                            # no problem
                            result = []
                        elif POL_MAX_RATE_MSG in payload['result'] or SEP_MAX_RATE_MSG in payload['result']:
                            print(f'(Should not happen) sleeping {self.SAFETY} ms')
                            # breakpoint()
                            throttled = True
                            time.sleep((self.SAFETY)/1000)
                        else:
                            print_error(f'Url {api_url_page} gave response {payload}')
                            # breakpoint()
                            return None
                    else:
                        if 'result' in payload:
                            result = payload['result']
                        elif 'error' in payload:
                            print_error(f"Url {api_url_page} gave error {payload['error']}")
                            return None
                        else:
                            raise Exception(f"Url {api_url_page} gave unknown answer {payload}")
                else:
                    print_error(f'Url {api_url_page} gave response {response.status_code}, {response}')
                    return None
            except requests.Timeout:
                # We retry increasing the attempt number
                print(f'Retrying call {api_url_page}, attempt {attempt+1}')
                return self.make_call(api_url=api_url_page, attempt=attempt+1)
            except requests.exceptions.RequestException as e:
                # This should catch all other requests exceptions
                raise Exception(f'Got {e} while calling {api_url_page}')
            if throttled:
                # We try again
                throttled = False
            elif not paginated:
                return result
            elif paginated and result == []:
                return results
            else:
                if result == None:
                    # Should not happen
                    raise Exception(f'Result is None while calling {api_url_page}')
                results.extend(result)
                if len(result) < offset:
                    # We got less than what we asked, return
                    return results
                else:
                    # We continue paginating
                    page = page + 1
                    # print(f'Paginating call {api_url_page}, page {page}')
                # breakpoint()

        

    def get_wallets(self, contracts:list[int]):
        wallets = []
        for contract in contracts:
            transactions = self.get_normal_transactions(contract)
            for transaction in transactions:
                if transaction['from'] != '':
                    adrs = HexStr2Int(transaction['from'])
                    if adrs not in wallets:
                        wallets.append(HexStr2Int(transaction['from']))
                if transaction['to'] != '':
                    adrs = HexStr2Int(transaction['to'])
                    if adrs not in wallets:
                        wallets.append(HexStr2Int(transaction['to']))
        return wallets


    def get_POL_balance(self, addresses:list[int]):
        """
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-a-single-address
            https://docs.polygonscan.com/amoy-polygonscan/api-endpoints/accounts#get-pol-balance-for-multiple-addresses-in-a-single-call
        """
        balances = None
        module = 'account'
        tag = 'latest'
        
        if len(addresses) > 1:
            action = 'balancemulti'
            addr_list = ','.join([Int2HexStr(address) for address in addresses])
            api_url = f'{self.endpoint}?module={module}&action={action}&address={addr_list}&tag={tag}&apikey={self.token}'
        else:
            action = 'balance'
            api_url = f'{self.endpoint}?module={module}&action={action}&address={Int2HexStr(addresses[0])}&tag={tag}&apikey={self.token}'

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
    
        api_url = f'{self.endpoint}?module={module}&action={action}&txhash={Int2HexStr(txhash,64)}&apikey={self.token}'
        result = self.make_call(api_url=api_url, paginated=False)
        # breakpoint()
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
