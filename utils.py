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

def Int2HexStr(numint:int) -> str:
    """
        Convert to hex with padding to get even length
    """
    enc_ln = len(hex(numint)) - len('0x')
    padd = enc_ln + enc_ln % 2
    # breakpoint()
    return f'0x{numint:0{padd}x}'