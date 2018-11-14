from stellar_base.keypair import Keypair
from stellar_base.address import Address
from stellar_base.builder import Builder
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.stellarxdr.StellarXDR_type import TimeBounds
from stellar_base.horizon import horizon_testnet
from secretsharing import PlaintextToHexSecretSharer
import requests
import hashlib
import datetime
import time
import base64


def initialize_keypair(add_funds=True):
    kp = Keypair.random()
    if add_funds:
        publickey = kp.address().decode()
        url = 'https://friendbot.stellar.org/?addr=' + publickey
        requests.get(url)
    return kp


def extract_x_from_tx(tx):
    return base64.b64decode(tx['_embedded']['records'][0]['signatures'][0]).decode()


PRIZE = '100'
PAWN = '100'
COUNTERPRIZE = '1'
DELTA = 60  # seconds

x = 'Hello, World!'  # Carol's message
x_a, x_b = PlaintextToHexSecretSharer.split_secret(x, 2, 2)

hash_x_a = hashlib.sha256(x_a.encode()).digest()
hash_x_b = hashlib.sha256(x_b.encode()).digest()
horizon = horizon_testnet()

print('Initializing keypairs')
kp_alice = initialize_keypair()
kp_bob = initialize_keypair()
kp_carol = initialize_keypair()

print('Carol creates accounts a_1 and a_2')
kp_a_1 = initialize_keypair(add_funds=False)
kp_a_2 = initialize_keypair(add_funds=False)
kp_a_1_address = kp_a_1.address().decode()
kp_a_2_address = kp_a_2.address().decode()
kp_a_1_seed = kp_a_1.seed().decode()
kp_a_2_seed = kp_a_2.seed().decode()
accounts_builder = Builder(secret=kp_carol.seed().decode())
accounts_builder.append_create_account_op(kp_a_1_address, '202.50009')
accounts_builder.append_create_account_op(kp_a_2_address, '202.50009')
accounts_builder.sign()
response = accounts_builder.submit()
assert 'hash' in response

print('Initializing transactions')
address_a_1 = Address(address=kp_a_1_address)
address_a_2 = Address(address=kp_a_2_address)
address_a_1.get()
address_a_2.get()

starting_sequence_a_1 = int(address_a_1.sequence)
starting_sequence_a_2 = int(address_a_2.sequence)

tau = datetime.datetime.now() + datetime.timedelta(seconds=30)
tau_unix = int(time.mktime(tau.timetuple()))
tau_plus_delta = tau + datetime.timedelta(seconds=DELTA)
tau_plus_delta_unix = int(time.mktime(tau_plus_delta.timetuple()))
tx_timebound = TimeBounds(
    minTime=tau_unix, maxTime=tau_plus_delta_unix)
counter_tx_timebound = TimeBounds(minTime=0, maxTime=tau_unix)

builder_t_1_1 = Builder(secret=kp_a_1_seed,
                        sequence=starting_sequence_a_1+1)
builder_t_1_1.append_payment_op(kp_alice.address().decode(), PRIZE, 'XLM')
builder_t_1_1.append_payment_op(kp_carol.address().decode(), PAWN, 'XLM')
builder_t_1_1.add_time_bounds(tx_timebound)
t_1_1 = builder_t_1_1.gen_tx()
hash_t_1_1 = builder_t_1_1.gen_te().hash_meta()

builder_t_1_2 = Builder(secret=kp_a_1_seed,
                        sequence=starting_sequence_a_1+1)
builder_t_1_2.append_payment_op(kp_bob.address().decode(), COUNTERPRIZE, 'XLM')
builder_t_1_2.add_time_bounds(counter_tx_timebound)
t_1_2 = builder_t_1_2.gen_tx()
hash_t_1_2 = builder_t_1_2.gen_te().hash_meta()

builder_t_2_2 = Builder(secret=kp_a_2_seed,
                        sequence=starting_sequence_a_2+1)
builder_t_2_2.append_payment_op(kp_bob.address().decode(), PRIZE, 'XLM')
builder_t_2_2.append_payment_op(kp_carol.address().decode(), PAWN, 'XLM')
builder_t_2_2.add_time_bounds(tx_timebound)
t_2_2 = builder_t_2_2.gen_tx()
hash_t_2_2 = builder_t_2_2.gen_te().hash_meta()

builder_t_2_1 = Builder(secret=kp_a_2_seed,
                        sequence=starting_sequence_a_2+1)
builder_t_2_1.append_payment_op(
    kp_alice.address().decode(), COUNTERPRIZE, 'XLM')
builder_t_2_1.add_time_bounds(counter_tx_timebound)
t_2_1 = builder_t_2_1.gen_tx()
hash_t_2_1 = builder_t_2_1.gen_te().hash_meta()

builder_t_1_0 = Builder(secret=kp_a_1_seed)
builder_t_1_0.append_set_options_op(master_weight=255)
builder_t_1_0.append_set_options_op(med_threshold=2)
builder_t_1_0.append_set_options_op(high_threshold=254)
builder_t_1_0.append_pre_auth_tx_signer(hash_t_1_2, 1)
builder_t_1_0.append_pre_auth_tx_signer(hash_t_1_1, 1)
builder_t_1_0.append_hashx_signer(hash_x_a, 1)
builder_t_1_0.append_set_options_op(master_weight=0)
builder_t_1_0.sign()

builder_t_2_0 = Builder(secret=kp_a_2_seed)
builder_t_2_0.append_set_options_op(master_weight=255)
builder_t_2_0.append_set_options_op(med_threshold=2)
builder_t_2_0.append_set_options_op(high_threshold=254)
builder_t_2_0.append_pre_auth_tx_signer(hash_t_2_1, 1)
builder_t_2_0.append_pre_auth_tx_signer(hash_t_2_2, 1)
builder_t_2_0.append_hashx_signer(hash_x_b, 1)
builder_t_2_0.append_set_options_op(master_weight=0)
builder_t_2_0.sign()

print('Submitting t_1_0')
response = builder_t_1_0.submit()
assert 'hash' in response

print('Submitting t_2_0')
response = builder_t_2_0.submit()
assert 'hash' in response

print('At this point Carol cannot remove funds from a_1/a_2')
builder = Builder(secret=kp_a_1_seed)
builder.append_payment_op(kp_carol.address().decode(), 1)
builder.sign()
response = builder.submit()
assert 'hash' not in response

print('Alice tries to submit t_1_1 before the deadline, but fails')
print(f'[deadline: { tau }; current time: { datetime.datetime.now() }]')
envelope = Te(t_1_1, opts={})
response = horizon.submit(envelope.xdr())
assert 'hash' not in response

print('We suppose Bob leaks his secret. Alice can submit t_2_1')
envelope = Te(t_2_1, opts={})
envelope.sign_hashX(x_b)
response = horizon.submit(envelope.xdr())
assert 'hash' in response

print('Waiting for the deadline')
tts = (tau - datetime.datetime.now()).total_seconds()
margin = 5
time.sleep(tts + margin)

print('Now Alice can submit t_1_1')
envelope = Te(t_1_1, opts={})
envelope.sign_hashX(x_a)
response = horizon.submit(envelope.xdr())
assert 'hash' in response

print('Bob cannot submit t_2_2, because he leaked the secret')
envelope = Te(t_2_2, opts={})
envelope.sign_hashX(x_b)
response = horizon.submit(envelope.xdr())
assert 'hash' not in response

print('At this point, the secret is public')
params = {'limit': 1, 'order': 'desc'}
last_tx_a_1 = horizon.account_transactions(kp_a_1_address, params=params)
last_tx_a_2 = horizon.account_transactions(kp_a_2_address, params=params)
x_a_1 = extract_x_from_tx(last_tx_a_1)
x_a_2 = extract_x_from_tx(last_tx_a_2)
assert PlaintextToHexSecretSharer.recover_secret([x_a_1, x_a_2]) == x
