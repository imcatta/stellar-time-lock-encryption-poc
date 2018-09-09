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

print('Carol creates rho and gamma')
kp_rho = initialize_keypair(add_funds=False)
kp_gamma = initialize_keypair(add_funds=False)
kp_rho_address = kp_rho.address().decode()
kp_gamma_address = kp_gamma.address().decode()
kp_rho_seed = kp_rho.seed().decode()
kp_gamma_seed = kp_gamma.seed().decode()
builder_rho_gamma = Builder(secret=kp_carol.seed().decode())
builder_rho_gamma.append_create_account_op(kp_rho_address, '202.50009')
builder_rho_gamma.append_create_account_op(kp_gamma_address, '202.50009')
builder_rho_gamma.sign()
response = builder_rho_gamma.submit()
assert 'hash' in response

print('Initializing transactions')
address_rho = Address(address=kp_rho_address)
address_gamma = Address(address=kp_gamma_address)
address_rho.get()
address_gamma.get()

starting_sequence_rho = int(address_rho.sequence)
starting_sequence_gamma = int(address_gamma.sequence)

tau = datetime.datetime.now() + datetime.timedelta(seconds=30)
tau_unix = int(time.mktime(tau.timetuple()))
tau_plus_delta = tau + datetime.timedelta(seconds=DELTA)
tau_plus_delta_unix = int(time.mktime(tau_plus_delta.timetuple()))
timebound_transazione = TimeBounds(
    minTime=tau_unix, maxTime=tau_plus_delta_unix)
timebound_controtransazione = TimeBounds(minTime=0, maxTime=tau_unix)

builder_rho_1 = Builder(secret=kp_rho_seed,
                        sequence=starting_sequence_rho+1)
builder_rho_1.append_payment_op(kp_bob.address().decode(), COUNTERPRIZE, 'XLM')
builder_rho_1.add_time_bounds(timebound_controtransazione)
tx_rho_1 = builder_rho_1.gen_tx()
hash_rho_1 = builder_rho_1.gen_te().hash_meta()

builder_rho_2 = Builder(secret=kp_rho_seed,
                        sequence=starting_sequence_rho+1)
builder_rho_2.append_payment_op(kp_alice.address().decode(), PRIZE, 'XLM')
builder_rho_2.append_payment_op(kp_carol.address().decode(), PAWN, 'XLM')
builder_rho_2.add_time_bounds(timebound_transazione)
tx_rho_2 = builder_rho_2.gen_tx()
hash_rho_2 = builder_rho_2.gen_te().hash_meta()

builder_gamma_1 = Builder(secret=kp_gamma_seed,
                          sequence=starting_sequence_gamma+1)
builder_gamma_1.append_payment_op(
    kp_alice.address().decode(), COUNTERPRIZE, 'XLM')
builder_gamma_1.add_time_bounds(timebound_controtransazione)
tx_gamma_1 = builder_gamma_1.gen_tx()
hash_gamma_1 = builder_gamma_1.gen_te().hash_meta()

builder_gamma_2 = Builder(secret=kp_gamma_seed,
                          sequence=starting_sequence_gamma+1)
builder_gamma_2.append_payment_op(kp_bob.address().decode(), PRIZE, 'XLM')
builder_gamma_2.append_payment_op(kp_carol.address().decode(), PAWN, 'XLM')
builder_gamma_2.add_time_bounds(timebound_transazione)
tx_gamma_2 = builder_gamma_2.gen_tx()
hash_gamma_2 = builder_gamma_2.gen_te().hash_meta()

builder_rho_0 = Builder(secret=kp_rho_seed)
builder_rho_0.append_set_options_op(master_weight=255)
builder_rho_0.append_set_options_op(med_threshold=2)
builder_rho_0.append_set_options_op(high_threshold=254)
builder_rho_0.append_pre_auth_tx_signer(hash_rho_1, 1)
builder_rho_0.append_pre_auth_tx_signer(hash_rho_2, 1)
builder_rho_0.append_hashx_signer(hash_x_a, 1)
builder_rho_0.append_set_options_op(master_weight=0)
builder_rho_0.sign()

builder_gamma_0 = Builder(secret=kp_gamma_seed)
builder_gamma_0.append_set_options_op(master_weight=255)
builder_gamma_0.append_set_options_op(med_threshold=2)
builder_gamma_0.append_set_options_op(high_threshold=254)
builder_gamma_0.append_pre_auth_tx_signer(hash_gamma_1, 1)
builder_gamma_0.append_pre_auth_tx_signer(hash_gamma_2, 1)
builder_gamma_0.append_hashx_signer(hash_x_b, 1)
builder_gamma_0.append_set_options_op(master_weight=0)
builder_gamma_0.sign()

print('Submitting rho_0')
response = builder_rho_0.submit()
assert 'hash' in response

print('Submitting gamma_0')
response = builder_gamma_0.submit()
assert 'hash' in response

print('At this point Carol cannot remove funds from rho/gamma')
builder = Builder(secret=kp_rho_seed)
builder.append_payment_op(kp_carol.address().decode(), 1)
builder.sign()
response = builder.submit()
assert 'hash' not in response

print('Alice tries to submit rho_2 before the deadline, but fails')
print(f'[deadline: { tau }; current time: { datetime.datetime.now() }]')
envelope = Te(tx_rho_2, opts={})
response = horizon.submit(envelope.xdr())
assert 'hash' not in response

print('Bob leaks his secret, so Alice can submit tx_gamma_1')
envelope = Te(tx_gamma_1, opts={})
envelope.sign_hashX(x_b)
response = horizon.submit(envelope.xdr())
assert 'hash' in response

print('Waiting for the deadline')
tts = (tau - datetime.datetime.now()).total_seconds()
time.sleep(tts)
time.sleep(5)  # some margin

print('Now Alice can submit tx_rho_2')
envelope = Te(tx_rho_2, opts={})
envelope.sign_hashX(x_a)
response = horizon.submit(envelope.xdr())
assert 'hash' in response

print('Bob cannot submit tx_gamma_2, because he leaked the secret')
envelope = Te(tx_gamma_2, opts={})
envelope.sign_hashX(x_b)
response = horizon.submit(envelope.xdr())
assert 'hash' not in response

print('At this point, the secret is public')
last_tx_rho = horizon.account_transactions(
    kp_rho_address, params={'limit': 1, 'order': 'desc'})
last_tx_gamma = horizon.account_transactions(
    kp_gamma_address, params={'limit': 1, 'order': 'desc'})
x_rho = base64.b64decode(
    last_tx_rho['_embedded']['records'][0]['signatures'][0]).decode()
x_gamma = base64.b64decode(
    last_tx_gamma['_embedded']['records'][0]['signatures'][0]).decode()
assert PlaintextToHexSecretSharer.recover_secret([x_rho, x_gamma]) == x
