package com.vpn.core.crypto;

import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/**
 * Simple key management: generate or load a symmetric AES key.
 */
public class KeyManager {
    private static final String ALGORITHM = "AES";
    private static final int KEY_SIZE = 256;

    public static SecretKey generateKey() throws CryptoException {
        try {
            KeyGenerator keyGen = KeyGenerator.getInstance(ALGORITHM);
            keyGen.init(KEY_SIZE);
            return keyGen.generateKey();
        } catch (NoSuchAlgorithmException e) {
            throw new CryptoException("AES not supported", e);
        }
    }

    public static SecretKey decodeKey(String base64) {
        byte[] decoded = Base64.getDecoder().decode(base64);
        return new SecretKeySpec(decoded, ALGORITHM);
    }

    public static String encodeKey(SecretKey key) {
        return Base64.getEncoder().encodeToString(key.getEncoded());
    }
}
