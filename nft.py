from datetime import datetime
from utils import Int2HexStr, HexStr2Int, print_error

class NFT:
    GOV_NFT = 'NftGovernance'
    GOV_CONTRACT = '0x88e0f9b16f5c3ff1f48576bf2dc785070c6a86a5'
    NFT_CREATION_ADR = HexStr2Int('0x0000000000000000000000000000000000000000')
    CREATED = 'created'
    SOLD = 'sold'
    BOUGHT = 'bought'
    GOV = 'governance'

    @classmethod
    def gen_key(cls, id, contractAddress):
        return f'{id}_{contractAddress}'
        # return id
    
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
            # breakpoint()

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
