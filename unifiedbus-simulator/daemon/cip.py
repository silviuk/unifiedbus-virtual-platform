"""
UnifiedBus CIP (Confidentiality and Integrity Protection) Engine
Implements hardware-accelerated Authenticated Encryption (AES-GCM / SM4-GCM emulation),
TokenID key binding, MAC tag authentication, and anti-replay sequence windows.
"""

import hmac
import hashlib
import struct
import time
from typing import Dict, Tuple, Optional

# CIP Cipher Suites defined in UB Base Specification 2.0
CIP_SUITE_NONE         = 0x00
CIP_SUITE_AES_128_GCM  = 0x01
CIP_SUITE_AES_256_GCM  = 0x02
CIP_SUITE_SM4_GCM      = 0x03


def _derive_key(token_id: int, secret_salt: bytes = b"UnifiedBus_CIP_Root_Key") -> bytes:
    token_bytes = struct.pack("!I", token_id)
    return hashlib.sha256(secret_salt + token_bytes).digest()


class CIPEngine:
    """
    Hardware-accelerated CIP security engine for UnifiedBus nodes and switches.
    """
    def __init__(self, cipher_suite: int = CIP_SUITE_AES_256_GCM, anti_replay_window_size: int = 64):
        self.cipher_suite = cipher_suite
        self.anti_replay_window_size = anti_replay_window_size
        self.highest_seq_seen: Dict[int, int] = {} # src_node -> highest seq
        self.replay_bitmap: Dict[int, int] = {}    # src_node -> 64-bit window bitmap
        self.total_encrypted_packets = 0
        self.total_decrypted_packets = 0
        self.total_tamper_rejections = 0
        self.total_replay_rejections = 0

    def encrypt_and_tag(self, payload: bytes, token_id: int, seq_num: int) -> Tuple[bytes, bytes]:
        """
        Encrypts payload and generates a 16-byte authentication tag (MAC).
        Returns (ciphertext, auth_tag).
        """
        if self.cipher_suite == CIP_SUITE_NONE or not payload:
            return payload, b"\x00" * 16

        key = _derive_key(token_id)
        # Keystream generation (ChaCha/AES-CTR style)
        nonce = struct.pack("!IQ", token_id, seq_num)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(payload):
            block_nonce = nonce + struct.pack("!I", counter)
            keystream.extend(hashlib.sha256(key + block_nonce).digest())
            counter += 1

        ciphertext = bytes(p ^ k for p, k in zip(payload, keystream[:len(payload)]))
        
        # Calculate MAC tag (Integrity Protection)
        tag_data = ciphertext + nonce + struct.pack("!B", self.cipher_suite)
        auth_tag = hmac.new(key, tag_data, hashlib.sha256).digest()[:16]
        
        self.total_encrypted_packets += 1
        return ciphertext, auth_tag

    def decrypt_and_verify(self, ciphertext: bytes, auth_tag: bytes, token_id: int, seq_num: int, src_node: int) -> Tuple[bool, bytes, str]:
        """
        Verifies authentication tag, checks anti-replay window, and decrypts payload.
        Returns (is_valid, plaintext, error_message).
        """
        if self.cipher_suite == CIP_SUITE_NONE or not ciphertext:
            return True, ciphertext, "OK"

        # 1. Anti-Replay Check
        if src_node in self.highest_seq_seen:
            highest = self.highest_seq_seen[src_node]
            diff = highest - seq_num
            if diff >= self.anti_replay_window_size:
                self.total_replay_rejections += 1
                return False, b"", f"CIP Replay Check: Stale sequence {seq_num} (highest={highest})"
            if diff >= 0:
                # Check if bit is already set in sliding bitmap
                if (self.replay_bitmap[src_node] & (1 << diff)) != 0:
                    self.total_replay_rejections += 1
                    return False, b"", f"CIP Replay Check: Duplicate sequence {seq_num} detected"
                self.replay_bitmap[src_node] |= (1 << diff)
            else:
                # Advance window
                shift = -diff
                if shift >= self.anti_replay_window_size:
                    self.replay_bitmap[src_node] = 1
                else:
                    self.replay_bitmap[src_node] = (self.replay_bitmap[src_node] << shift) | 1
                self.highest_seq_seen[src_node] = seq_num
        else:
            self.highest_seq_seen[src_node] = seq_num
            self.replay_bitmap[src_node] = 1

        # 2. Cryptographic Integrity Verification
        key = _derive_key(token_id)
        nonce = struct.pack("!IQ", token_id, seq_num)
        tag_data = ciphertext + nonce + struct.pack("!B", self.cipher_suite)
        expected_tag = hmac.new(key, tag_data, hashlib.sha256).digest()[:16]

        if not hmac.compare_digest(auth_tag, expected_tag):
            self.total_tamper_rejections += 1
            return False, b"", "CIP Integrity Error: Cryptographic MAC tag verification failed (tampering detected)"

        # 3. Decrypt Plaintext
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            block_nonce = nonce + struct.pack("!I", counter)
            keystream.extend(hashlib.sha256(key + block_nonce).digest())
            counter += 1

        plaintext = bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))
        self.total_decrypted_packets += 1
        return True, plaintext, "OK"
