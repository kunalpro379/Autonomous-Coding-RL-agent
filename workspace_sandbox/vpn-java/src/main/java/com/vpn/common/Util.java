package com.vpn.common;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

public class Util {
    public static byte[] intToBytes(int value) {
        return new byte[] {
            (byte) (value >>> 24),
            (byte) (value >>> 16),
            (byte) (value >>> 8),
            (byte) value
        };
    }

    public static int bytesToInt(byte[] bytes) {
        return ((bytes[0] & 0xFF) << 24) |
               ((bytes[1] & 0xFF) << 16) |
               ((bytes[2] & 0xFF) << 8) |
               (bytes[3] & 0xFF);
    }

    public static byte[] readFully(DataInputStream in, int length) throws IOException {
        byte[] buffer = new byte[length];
        int totalRead = 0;
        while (totalRead < length) {
            int read = in.read(buffer, totalRead, length - totalRead);
            if (read == -1) {
                throw new IOException("Premature end of stream");
            }
            totalRead += read;
        }
        return buffer;
    }
}
