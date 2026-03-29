package com.vpn.crypto;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;

/**
 * Handles Diffie‑Hellman key exchange and AES‑GCM encryption/decryption.
 */
public class CipherEngine {
    private static final String DH_ALG = "DH";
    private static final String AES_ALG = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int GCM_TAG_LENGTH = 128;
    private static final int AES_KEY_SIZE = 256;

    private PrivateKey privateKey;
    private PublicKey publicKey;
    private SecretKey sessionKey;
    private byte[] iv;

    public void generateKeyPair() throws CryptoException {
        try {
            KeyPairGenerator kpg = KeyPairGenerator.getInstance(DH_ALG);
            kpg.initialize(AES_KEY_SIZE);
            KeyPair kp = kpg.generateKeyPair();
            privateKey = kp.getPrivate();
            publicKey = kp.getPublic();
        } catch (NoSuchAlgorithmException e) {
            throw new CryptoException("DH algorithm not available", e);
        }
    }

    public byte[] getPublicKeyBytes() {
        return publicKey.getEncoded();
    }

    public void deriveSessionKey(byte[] peerPublicKeyBytes) throws CryptoException {
        try {
            KeyFactory kf = KeyFactory.getInstance(DH_ALG);
            PublicKey peerPublicKey = kf.generatePublic(new X509EncodedKeySpec(peerPublicKeyBytes));
            KeyAgreement ka = KeyAgreement.getInstance(DH_ALG);
            ka.init(privateKey);
            ka.doPhase(peerPublicKey, true);
            byte[] sharedSecret = ka.generateSecret();
            // Derive AES key using SHA‑256
            MessageDigest digest = MessageDigest.getInstance("SHA‑256");
            byte[] keyMaterial = digest.digest(sharedSecret);
            sessionKey = new SecretKeySpec(keyMaterial, AES_ALG);
            // Generate a random IV (12 bytes for GCM)
            SecureRandom random = new SecureRandom();
            iv = new byte[12];
            random.nextBytes(iv);
        } catch (Exception e) {
            throw new CryptoException("Key derivation failed", e);
        }
    }

    public byte[] encrypt(byte[] plaintext) throws CryptoException {
        try {
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.ENCRYPT_MODE, sessionKey, spec);
            byte[] ciphertext = cipher.doFinal(plaintext);
            // Prepend IV for the other side
            byte[] result = new byte[iv.length + ciphertext.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(ciphertext, 0, result, iv.length, ciphertext.length);
            return result;
        } catch (Exception e) {
            throw new CryptoException("Encryption failed", e);
        }
    }

    public byte[] decrypt(byte[] ciphertextWithIv) throws CryptoException {
        try {
            if (ciphertextWithIv.length < iv.length) {
                throw new CryptoException("Ciphertext too short");
            }
            byte[] iv = Arrays.copyOfRange(ciphertextWithIv, 0, this.iv.length);
            byte[] ciphertext = Arrays.copyOfRange(ciphertextWithIv, this.iv.length, ciphertextWithIv.length);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.DECRYPT_MODE, sessionKey, spec);
            return cipher.doFinal(ciphertext);
        } catch (Exception e) {
            throw new CryptoException("Decryption failed", e);
        }
    }

    public boolean isReady() {
        return sessionKey != null;
    }
}
