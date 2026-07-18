import * as anchor from '@coral-xyz/anchor';
import { Connection, PublicKey, SystemProgram, Transaction } from '@solana/web3.js';
import {
  ASSOCIATED_TOKEN_PROGRAM_ID,
  TOKEN_2022_PROGRAM_ID,
  getAssociatedTokenAddressSync,
  createAssociatedTokenAccountInstruction,
} from '@solana/spl-token';
import axios from 'axios';
import idlJson from './idl.json';

// ----- Devnet settings (copied straight from TxLINE's docs/repo) -----
const RPC_URL = 'https://api.devnet.solana.com';
const PROGRAM_ID = new PublicKey('6pW64gN1s2uqjHkn1unFeEjAwJkPGHoppGvS715wyP2J');
const TXL_MINT = new PublicKey('4Zao8ocPhmMgq7PdsYWyxvqySMGx7xb9cMftPMkEokRG');
const API_BASE_URL = 'https://txline-dev.txodds.com/api';
const JWT_URL = 'https://txline-dev.txodds.com/auth/guest/start';
const SERVICE_LEVEL_ID = 1; // free World Cup tier
const WEEKS = 4; // minimum allowed, must be a multiple of 4
const SELECTED_LEAGUES = []; // empty = standard free bundle

const connectButton = document.querySelector('#connect');
const subscribeButton = document.querySelector('#subscribe');
const statusText = document.querySelector('#status');

function log(msg) {
  console.log(msg);
  statusText.textContent = msg;
}

// ----- Button 1: Connect (same as before) -----
connectButton.addEventListener('click', async () => {
  if (!window.solana || !window.solana.isPhantom) {
    log('Phantom not found.');
    return;
  }
  const resp = await window.solana.connect();
  log(`Connected: ${resp.publicKey.toString()}`);
});

// ----- Button 2: Subscribe + Activate -----
subscribeButton.addEventListener('click', async () => {
  try {
    if (!window.solana?.isConnected) {
      log('Connect Phantom first.');
      return;
    }

    const connection = new Connection(RPC_URL, 'confirmed');
    const provider = new anchor.AnchorProvider(connection, window.solana, { commitment: 'confirmed' });
    anchor.setProvider(provider);

    // Point the IDL at the DEVNET program address (the file itself lists mainnet's).
    const idl = { ...idlJson, address: PROGRAM_ID.toBase58() };
    const program = new anchor.Program(idl, provider);

    const userPubkey = window.solana.publicKey;

    log('Checking your token account...');
    const userTokenAccount = getAssociatedTokenAddressSync(
      TXL_MINT, userPubkey, false, TOKEN_2022_PROGRAM_ID
    );

    // If this account doesn't exist yet on-chain, create it first.
    const existing = await connection.getAccountInfo(userTokenAccount);
    if (!existing) {
      log('Creating your token account (approve in Phantom)...');
      const createTx = new Transaction().add(
        createAssociatedTokenAccountInstruction(
          userPubkey, userTokenAccount, userPubkey, TXL_MINT,
          TOKEN_2022_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
        )
      );
      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
      createTx.recentBlockhash = blockhash;
      createTx.feePayer = userPubkey;
      const signedCreateTx = await window.solana.signTransaction(createTx);
      const createSig = await connection.sendRawTransaction(signedCreateTx.serialize());
      await connection.confirmTransaction({ signature: createSig, blockhash, lastValidBlockHeight }, 'confirmed');
      log('Token account created.');
    }

    // Work out the two special addresses ("PDAs") the contract needs.
    const [pricingMatrixPda] = PublicKey.findProgramAddressSync(
      [Buffer.from('pricing_matrix')], program.programId
    );
    const [tokenTreasuryPda] = PublicKey.findProgramAddressSync(
      [Buffer.from('token_treasury_v2')], program.programId
    );
    const tokenTreasuryVault = getAssociatedTokenAddressSync(
      TXL_MINT, tokenTreasuryPda, true, TOKEN_2022_PROGRAM_ID
    );

    // Build the "subscribe" transaction.
    log('Building subscribe transaction...');
    const tx = await program.methods
      .subscribe(SERVICE_LEVEL_ID, WEEKS)
      .accounts({
        user: userPubkey,
        pricingMatrix: pricingMatrixPda,
        tokenMint: TXL_MINT,
        userTokenAccount: userTokenAccount,
        tokenTreasuryVault: tokenTreasuryVault,
        tokenTreasuryPda: tokenTreasuryPda,
        tokenProgram: TOKEN_2022_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        associatedTokenProgram: ASSOCIATED_TOKEN_PROGRAM_ID,
      })
      .transaction();

    const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
    tx.recentBlockhash = blockhash;
    tx.feePayer = userPubkey;

    log('Approve the subscribe transaction in Phantom...');
    const signedTx = await window.solana.signTransaction(tx);
    const txSig = await connection.sendRawTransaction(signedTx.serialize());
    await connection.confirmTransaction({ signature: txSig, blockhash, lastValidBlockHeight }, 'confirmed');
    log(`Subscribed! Tx: ${txSig}`);

    // ----- Now activate the API key -----
    log('Getting a login token...');
    const authResponse = await axios.post(JWT_URL);
    const jwt = authResponse.data.token;

    const messageString = `${txSig}:${SELECTED_LEAGUES.join(',')}:${jwt}`;
    const messageBytes = new TextEncoder().encode(messageString);

    log('Approve the signature request in Phantom...');
    const { signature } = await window.solana.signMessage(messageBytes, 'utf8');
    const walletSignature = Buffer.from(signature).toString('base64');

    log('Activating your API token...');
    const activationResponse = await axios.post(
      `${API_BASE_URL}/token/activate`,
      { txSig, walletSignature, leagues: SELECTED_LEAGUES },
      { headers: { Authorization: `Bearer ${jwt}` } }
    );

    const apiToken = activationResponse.data.token || activationResponse.data;
    log(`DONE. API token: ${apiToken}`);
    console.log('JWT (guest token):', jwt);
    console.log('API token:', apiToken);
  } catch (err) {
    console.error(err);
    log(`Error: ${err.message}`);
  }
});