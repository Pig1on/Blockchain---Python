import hashlib
import json
from time import time
from urllib.parse import urlparse  # URL parsing
import uuid  # Generating unique ID
from flask import Flask, jsonify, request
from typing import Any, Dict, List
import requests
from argparse import ArgumentParser  # Command line argument parsing

node_identifier = str(uuid.uuid4()).replace('-', '')


class Blockchain:
    def __init__(self):
        self.chain = []  # Storage block
        self.current_transactions = []  # Transaction entity
        self.nodes = set()  # A set of nodes without duplicates

        # Create Genesis Block
        self.new_block(previous_hash='1', proof=100)

    def new_block(self, proof: int, previous_hash=None):  # New block
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block),
        }
        self.current_transactions = []  # Reset the current transaction information after the new block is packaged
        self.chain.append(block)  # Add the new block to the chain
        return block

    def new_transaction(self, sender: str, recipient: str, amount: int) -> int:
        """Add a new transaction

        Args:
            sender (str): Sender
            recipient (str): Recipient
            amount (int): Amount

        Returns:
            int: Returns the block number that will contain this transaction
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block: Dict[str, Any]) -> str:
        """Calculate hash value, return the hash digest

        Args:
            block (Dict[str, Any]): Input a block

        Returns:
            str: Digest information
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):  # Get the last block in the current chain
        return self.chain[-1]  # Return the last block in the chain

    def proof_of_work(self, last_proof: int) -> int:
        """Work calculation, compute a hash that meets requirements

        Args:
            last_proof (int): The proof of the previous block

        Returns:
            int: Returns the proof that meets requirements
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    def valid_chain(self, chain: List[Dict[str, Any]]) -> bool:
        """Verify the chain is valid: longest and valid

        Args:
            chain (List[Dict[str, Any]]): Input chain

        Returns:
            bool: Returns whether it is valid
        """
        last_block = chain[0]  # Start from the first genesis block
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Verify that the proof of work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def valid_proof(self, last_proof: int, proof: int) -> bool:

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        if guess_hash[:4] == "0000":
            return True
        else:
            return False

    def register_node(self, address: str) -> None:
        """Add a new node to the set of nodes

        Args:
            address (str): Node address. Eg: "http://127.0.0.1:5002"
        """
        parsed_url = urlparse(address)  # Parse URL
        self.nodes.add(parsed_url.netloc)  # Get the domain name

    def resolve_conflicts(self) -> bool:

        neighbours = self.nodes  # Obtain node information
        new_chain = None  # Define possible new chains

        max_length = len(self.chain)  # Get the current chain length

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

# Flask Web Application Interface
app = Flask(__name__)
blockchain = Blockchain()

# Add a new transaction interface
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing parameters', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to block {index}'}
    return jsonify(response), 201

# Package block interface
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block  # Get the information of the last block on the chain
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # The sender "0" indicates that this is a newly mined coin, providing a reward for the miner
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    block = blockchain.new_block(proof, None)  # Generate a new block

    response = {
        'message': "New block has been successfully packaged and generated!",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

# View chain interface
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

# Node registration interface
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please provide a valid node list", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added!',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


# Consensus interface
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {'message': 'The current chain was not compliant and has been replaced', 'new_chain': blockchain.chain}
    else:
        response = {'message': 'The current chain complies with the requirements', 'chain': blockchain.chain}

    return jsonify(response), 200


if __name__ == "__main__":
    parser = ArgumentParser()  # Command-line argument parsing, default port is 5000
    parser.add_argument('-p',
                        '--port',
                        default=5000,
                        type=int,
                        help='port to listen on')
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port)
