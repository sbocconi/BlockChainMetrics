from datetime import datetime
from polygonscan import PolygonScan
from utils import Int2HexStr, HexStr2Int
from nft import NFT

TRANS_CACHE = {}


class AddressTransactions:

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
                print(f'Transaction hash {Int2HexStr(txhash)} not found, trying to retrieve it')
                transaction = self.ps.get_transaction(txhash)

                if transaction == None:
                    # We fall back to calculating each transaction
                    # for the other address
                    # breakpoint()
                    if self.address == tr_from:
                        self.get_transactions(address=tr_to)
                    else:
                        self.get_transactions(address=tr_from)
                    
                    transaction = self.retrieve_transaction(txhash)
                    
                    if transaction == None:
                        # Nothing to do anymore
                        raise Exception(f'Transaction hash {Int2HexStr(txhash)} not found')

            # breakpoint()
            nft = self.retrieve_nft(tokenID, contractAddress)
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

    def retrieve_nft(self, id, contractAddress):
        key = NFT.gen_key(id, contractAddress)
        for nft in self.NFTs:
            if nft.id == key:
                return nft
        nft = NFT(key)
        self.NFTs.append(nft)
        return nft

    def retrieve_transaction(self, txhash):
        if Int2HexStr(txhash) in TRANS_CACHE:
            return TRANS_CACHE[Int2HexStr(txhash)]
        return None
        # print(f'Transaction hash {txhash} not found')
        # return None
        