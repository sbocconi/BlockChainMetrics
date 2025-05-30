import yaml
from pathlib import Path

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

def Int2HexStr(numint:int, length:int=None) -> str:
    """
        Convert to hex with padding to get even length
        or to given length
    """
    if length == None:
        enc_ln = len(hex(numint)) - len('0x')
        padd = enc_ln + enc_ln % 2
    else:
        padd = length
    # breakpoint()
    return f'0x{numint:0{padd}x}'

def check_dict(tr):
    if type(tr) != dict or len(tr.keys()) == 0:
        print(f"Expected non-empty dict but got {tr}: likely some problem with the http call")
        breakpoint()

def make_percentage(nmbr:float, digits:int=2)-> float:

    return int(nmbr*100*(10**digits))/100