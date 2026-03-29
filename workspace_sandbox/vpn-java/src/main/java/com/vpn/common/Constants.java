package com.vpn.common;

public final class Constants {
    // Frame types
    public static final byte FRAME_DATA = 0x01;
    public static final byte FRAME_CONTROL = 0x02;
    public static final byte FRAME_KEEPALIVE = 0x03;

    // Default server port
    public static final int DEFAULT_PORT = 5555;

    // TUN device name prefix
    public static final String TUN_DEVICE_PREFIX = "vpnjava";

    // Virtual network IP range (server: 10.8.0.1, client: 10.8.0.2)
    public static final String VIRTUAL_NETWORK = "10.8.0.0/24";
    public static final String SERVER_VIRTUAL_IP = "10.8.0.1";
    public static final String CLIENT_VIRTUAL_IP = "10.8.0.2";

    // Encryption
    public static final String CIPHER_ALGORITHM = "AES/GCM/NoPadding";
    public static final int AES_KEY_SIZE = 256;
    public static final int GCM_TAG_LENGTH = 128;
    public static final String KEY_EXCHANGE_ALGORITHM = "DH";

    private Constants() {}
}
