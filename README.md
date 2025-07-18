# BlockChainMetrics
## Introduction
Given addresses used on a Blockchain (Polygon or Sepolia), retrieves transaction data and calculate metrics such as average NFTs sold per address.

Here the output of a run with 3 addresses:

![alt Screenshot output](figs/Screenshot%202025-05-20%20at%2012.33.23.png)

## Usage

You need to copy file `.settings.yaml.example` to `.settings.yaml` and edit that file providing your own API token for [Polygon](https://polygonscan.com/) and [Sepolia](https://sepolia.etherscan.io/).

You need to provide a file of addresses, copy `addresses.yaml.example` to `addresses.yaml` and provide the wallet addresses under `wallets`.

Then to run the program run the folllowing command from a directory above the repo directory:

```
python -m BlockChainMetrics.main -n <network>
```

Have a look at the code for more options.

## Acknowledgements

This software has been developed in the scope of the [Dafne+ project](https://dafneplus.eu/).

<img src="https://upload.wikimedia.org/wikipedia/commons/8/84/European_Commission.svg"
     width="190" alt="Project funded by the European Commission">

Dafne+ has received funding from the European Union's Horizon Europe Research and Innovation programme under Grant Agreement No. 101061548.
