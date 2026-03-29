package com.vpn.crypto;

import org.bouncycastle.crypto.agreement.DHBasicAgreement;
import org.bouncycastle.crypto.generators.DHBasicKeyPairGenerator;
import org.bouncycastle.crypto.params.DHKeyGenerationParameters;
import org.bouncycastle.crypto.params.DHParameters;
import org.bouncycastle.crypto.params.DHPrivateKeyParameters;
import org.bouncycastle.crypto.params.DHPublicKeyParameters;
import java.math.BigInteger;
import java.security.SecureRandom;

/**
 * Diffie‑Hellman key exchange using BouncyCastle.
 * Generates a shared secret for symmetric encryption.
 */
public class KeyExchange {
    private static final BigInteger P = new BigInteger("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
            + "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
            + "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
            + "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
            + "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381"
            + "FFFFFFFFFFFFFFFF", 16);
    private static final BigInteger G = BigInteger.valueOf(2);

    private DHPrivateKeyParameters privateKey;
    private DHPublicKeyParameters publicKey;

    public KeyExchange() {
        DHParameters dhParams = new DHParameters(P, G);
        DHKeyGenerationParameters params = new DHKeyGenerationParameters(new SecureRandom(), dhParams);
        DHBasicKeyPairGenerator gen = new DHBasicKeyPairGenerator();
        gen.init(params);
        org.bouncycastle.crypto.AsymmetricCipherKeyPair pair = gen.generateKeyPair();
        privateKey = (DHPrivateKeyParameters) pair.getPrivate();
        publicKey = (DHPublicKeyParameters) pair.getPublic();
    }

    public byte[] getPublicKeyBytes() {
        return publicKey.getY().toByteArray();
    }

    public byte[] computeSharedSecret(byte[] peerPublicKeyBytes) throws CryptoException {
        try {
            BigInteger peerY = new BigInteger(peerPublicKeyBytes);
            DHPublicKeyParameters peerPublic = new DHPublicKeyParameters(peerY, publicKey.getParameters());
            DHBasicAgreement agreement = new DHBasicAgreement();
            agreement.init(privateKey);
            BigInteger secret = agreement.calculateAgreement(peerPublic);
            return secret.toByteArray();
        } catch (Exception e) {
            throw new CryptoException("Failed to compute shared secret", e);
        }
    }
}
