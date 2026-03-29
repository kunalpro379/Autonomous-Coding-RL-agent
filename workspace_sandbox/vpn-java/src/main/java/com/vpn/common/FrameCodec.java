package com.vpn.common;

import java.nio.ByteBuffer;
import java.util.zip.CRC32;

/**
 * Encodes/decodes tunnel frames.
 * Frame format:
 *   uint8  type (0=data, 1=control, 2=keepalive)
 *   uint32 length (payload length)
 *   uint32 crc32 (checksum of header+payload)
 *   byte[] payload
 */
public class FrameCodec {
    public static final int HEADER_SIZE = 9;
    public static final byte TYPE_DATA = 0;
    public static final byte TYPE_CONTROL = 1;
    public static final byte TYPE_KEEPALIVE = 2;

    public static byte[] encodeFrame(byte type, byte[] payload) {
        ByteBuffer buf = ByteBuffer.allocate(HEADER_SIZE + payload.length);
        buf.put(type);
        buf.putInt(payload.length);
        buf.putInt(0);
        buf.put(payload);
        buf.flip();
        CRC32 crc = new CRC32();
        crc.update(buf.array(), 0, buf.limit());
        int checksum = (int) crc.getValue();
        buf.putInt(5, checksum);
        return buf.array();
    }

    public static DecodedFrame decodeFrame(byte[] frame) throws IllegalArgumentException {
        if (frame.length < HEADER_SIZE) {
            throw new IllegalArgumentException("Frame too short");
        }
        ByteBuffer buf = ByteBuffer.wrap(frame);
        byte type = buf.get();
        int length = buf.getInt();
        int receivedCrc = buf.getInt();
        if (frame.length != HEADER_SIZE + length) {
            throw new IllegalArgumentException("Length mismatch");
        }
        CRC32 crc = new CRC32();
        crc.update(frame, 0, HEADER_SIZE + length);
        int computedCrc = (int) crc.getValue();
        if (receivedCrc != computedCrc) {
            throw new IllegalArgumentException("CRC mismatch");
        }
        byte[] payload = new byte[length];
        buf.get(payload);
        return new DecodedFrame(type, payload);
    }

    public static class DecodedFrame {
        public final byte type;
        public final byte[] payload;

        public DecodedFrame(byte type, byte[] payload) {
            this.type = type;
            this.payload = payload;
        }
    }
}
