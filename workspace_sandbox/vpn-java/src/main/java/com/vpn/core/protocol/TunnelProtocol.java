package com.vpn.core.protocol;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Simple framing protocol for tunnel packets.
 * Frame format:
 *   [ type:1 byte ] [ length:2 bytes (unsigned) ] [ payload:length bytes ]
 */
public class TunnelProtocol {
    public static final byte TYPE_DATA = 0x01;
    public static final byte TYPE_CONTROL = 0x02;
    public static final int MAX_FRAME_SIZE = 65535;

    public static byte[] encodeFrame(byte type, byte[] payload) {
        if (payload.length > 65535) {
            throw new IllegalArgumentException("Payload too large");
        }
        ByteBuffer buf = ByteBuffer.allocate(3 + payload.length);
        buf.order(ByteOrder.BIG_ENDIAN);
        buf.put(type);
        buf.putShort((short) payload.length);
        buf.put(payload);
        return buf.array();
    }

    public static Frame decodeFrame(ByteBuffer buffer) throws ProtocolException {
        if (buffer.remaining() < 3) {
            return null; // need more data
        }
        buffer.mark();
        byte type = buffer.get();
        int length = buffer.getShort() & 0xFFFF;
        if (buffer.remaining() < length) {
            buffer.reset();
            return null; // incomplete frame
        }
        byte[] payload = new byte[length];
        buffer.get(payload);
        return new Frame(type, payload);
    }

    public static class Frame {
        private final byte type;
        private final byte[] payload;

        public Frame(byte type, byte[] payload) {
            this.type = type;
            this.payload = payload;
        }

        public byte getType() { return type; }
        public byte[] getPayload() { return payload; }
    }

    public static class ProtocolException extends Exception {
        public ProtocolException(String message) { super(message); }
    }
}
