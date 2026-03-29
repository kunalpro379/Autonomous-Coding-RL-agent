package com.vpn.core.crypto;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import java.nio.ByteBuffer;
import java.security.SecureRandom;

/**
 * Encrypts/decrypts packets using AES‑GCM.
 * Each packet gets a fresh 12‑byte nonce, prepended to the ciphertext.
 */
public class PacketEncryptor {
    private static final String ALGORITHM = "AES/GCM/NoPadding";
    private static final int TAG_LENGTH_BIT = 128;
    private static final int NONCE_LENGTH = 12;

    private final SecretKey key;
    private final SecureRandom random;

    public PacketEncryptor(SecretKey key) {
        this.key = key;
        this.random = new SecureRandom();
    }

    /**
     * Encrypt plaintext, returning nonce + ciphertext in a new ByteBuffer.
     */
    public ByteBuffer encrypt(ByteBuffer plaintext) throws CryptoException {
        try {
            byte[] nonce = new byte[NONCE_LENGTH];
            random.nextBytes(nonce);

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            GCMParameterSpec spec = new GCMParameterSpec(TAG_LENGTH_BIT, nonce);
            cipher.init(Cipher.ENCRYPT_MODE, key, spec);

            byte[] ciphertext = cipher.doFinal(plaintext.array(),
                    plaintext.position(), plaintext.remaining());

            // Allocate: nonce + ciphertext
            ByteBuffer result = ByteBuffer.allocate(NONCE_LENGTH + ciphertext.length);
            result.put(nonce);
            result.put(ciphertext);
            result.flip();
            return result;
        } catch (Exception e) {
            throw new CryptoException("Encryption failed", e);
        }
    }

    /**
     * Decrypt nonce + ciphertext back to plaintext.
     */
    public ByteBuffer decrypt(ByteBuffer encrypted) throws CryptoException {
        try {
            if (encrypted.remaining() < NONCE_LENGTH) {
                throw new CryptoException("Packet too short for nonce");
            }
            byte[] nonce = new byte[NONCE_LENGTH];
            encrypted.get(nonce);

            byte[] ciphertext = new byte[encrypted.remaining()];
            encrypted.get(ciphertext);

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            GCMParameterSpec spec = new GCMParameterSpec(TAG_LENGTH_BIT, nonce);
            cipher.init(Cipher.DECRYPT_MODE, key, spec);

            byte[] plaintext = cipher.doFinal(ciphertext);
            return ByteBuffer.wrap(plaintext);
        } catch (Exception e) {
            throw new CryptoException("Decryption failed", e);
        }
    }
}
