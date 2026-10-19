import argparse
from .feed import generate
from .model import Engine
from .protocol import encode

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=20)
parser.add_argument('--seed', type=int, default=1)
args = parser.parse_args()
engine = Engine()
print('sequence,price,quantity,order,position,killed,packet_hex')
for quote in generate(args.count, args.seed):
    order, position, killed = engine.step(quote)
    print(f'{quote.sequence},{quote.price},{quote.quantity},{order},{position},{killed},{encode(quote).hex()}')
