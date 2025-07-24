#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py --test prod-like; sleep 1; done

import argparse
from collections import deque
from enum import Enum
import time
import socket
import json

# libs for animating ticker
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "CHARIZARD"

# ~~~~~============== MAIN LOOP ==============~~~~~

class Order:
    def __init__(self, id_, symbol, dir_, price, size):
        self.id_ = id_
        self.symbol = symbol
        self.dir_ = dir_
        self.price = price
        self.size = size

    def __str__(self):
        return (
            f"Id {self.id_}: {self.dir_} {self.size} of {self.symbol} for ${self.price}"
        )

    def send(self, exchange):
        exchange.send_add_message(
            order_id=self.id_,
            symbol=self.symbol,
            dir=self.dir_,
            price=self.price,
            size=self.size,
        )

class StateManager:
    def __init__(self, exchange):
        """Set up data structures to keep track of various trading bot states,
        like positions, orders and so on"""
        self.exchange = exchange
        self.positions = {}
        self.unacked_orders = {}
        self.open_orders = {}
        # Start ids at -1 because we always increment when getting the next ID
        self.cur_id = -1

    def next_id(self):
        """Returns a fresh order id for the next order"""
        self.cur_id += 1
        return self.cur_id

    def new_order(self, symbol, dir_, price, size):
        """Sends a new order and keeps track of it in our state"""
        order_id = self.next_id()
        order = Order(order_id, symbol, dir_, price, size)
        print(f"Sending order {order}")
        order.send(self.exchange)
        self.unacked_orders[order_id] = order

    def on_hello(self, hello_message):
        """Handle a hello message by setting our current positions"""
        symbol_positions = hello_message["symbols"]
        for symbol_position in symbol_positions:
            symbol = symbol_position["symbol"]
            position = symbol_position["position"]
            self.positions[symbol] = position
        print(self.positions)

    def on_ack(self, message):
        """Handle an ack by marking the order as live"""
        order_id = message["order_id"]
        if order_id in self.unacked_orders:
            self.open_orders[order_id] = self.unacked_orders.pop(order_id)
            print("Got ack on order", self.open_orders[order_id])
        else:
            print("Unexpectedly got ack on unknown order_id", order_id)

    def on_out(self, message):
        """Handle an out by removing the order"""
        order_id = message["order_id"]
        if order_id in self.open_orders:
            order = self.open_orders.pop(order_id)
            print(f"Got out on order {order}")
        else:
            print("Unexpectedly got out on unknown order_id", order_id)

    def on_fill(self, message):
        """Handle a fill by decrementing the open size of the order and updating our
        positions"""
        order_id = message["order_id"]
        symbol = message["symbol"]
        dir_ = message["dir"]
        raw_size = message["size"]
        size_multiplier = 1 if dir_ == Dir.BUY.value else -1
        size = raw_size * size_multiplier
        self.positions[symbol] = self.positions.get(symbol, 0) + size
        if order_id in self.open_orders:
            self.open_orders[order_id].size -= raw_size
        else:
            print(
                "Unexpectedly got fill on order_id that we did not expect to be live",
                order_id,
            )


def main():
    args = parse_arguments()

    exchange = ExchangeConnection(args=args)
    state_manager = StateManager(exchange)

    # Store and print the "hello" message received from the exchange. This
    # contains useful information about your positions. Normally you start with
    # all positions at zero, but if you reconnect during a round, you might
    # have already bought/sold symbols and have non-zero positions.
    hello_message = exchange.read_message()
    state_manager.on_hello(hello_message)

    # Uncomment the following two lines! This will send two QROLL orders: one to buy 100
    # QROLL for $950, and the other to sell 100 QROLL for $1050.
    #
    # state_manager.new_order("QROLL", Dir.BUY, 950, 100)
    # state_manager.new_order("QROLL", Dir.SELL, 1050, 100)

    # Here is the main loop of the program. It will continue to read and
    # process messages in a loop until a "close" message is received. You
    # should write to code handle more types of messages (and not just print
    # the message). Feel free to modify any of the starter code below.
    #
    # Note: a common mistake people make is to call write_message() at least
    # once for every read_message() response.
    #
    # Every message sent to the exchange generates at least one response
    # message. Sending a message in response to every exchange message will
    # cause a feedback loop where your bot's messages will quickly be
    # rate-limited and ignored. Please, don't do that!
    while True:
        message = exchange.read_message()

        # Some of the message types below happen infrequently and contain
        # important information to help you understand what your bot is doing,
        # so they are printed in full. We recommend not always printing every
        # message because it can be a lot of information to read. Instead, let
        # your code handle the messages and just print the information
        # important for you!
        if message["type"] == "close":
            print("The round has ended")
            break
        elif message["type"] == "error":
            print(message)
        elif message["type"] == "reject":
            print(message)
        elif message["type"] == "ack":
            state_manager.on_ack(message)
        elif message["type"] == "out":
            state_manager.on_out(message)
        elif message["type"] == "fill":
            state_manager.on_fill(message)
        elif message["type"] == "book":
            pass


# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questions about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to


class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)
        self.reader = exchange_socket.makefile("r", 1)
        self.writer = exchange_socket

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.reader.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(
        self, order_id: int, symbol: str, dir: Dir, price: int, size: int
    ):
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s

    def _write_message(self, message):
        what_to_write = json.dumps(message)
        if not what_to_write.endswith("\n"):
            what_to_write = what_to_write + "\n"

        length_to_send = len(what_to_write)
        total_sent = 0
        while total_sent < length_to_send:
            sent_this_time = self.writer.send(
                what_to_write[total_sent:].encode("utf-8")
            )
            if sent_this_time == 0:
                raise Exception("Unable to send data to exchange")
            total_sent += sent_this_time

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 22000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args


if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLAC" + "EME"
    ), "Please put your team name in the variable [team_name]."

    main()