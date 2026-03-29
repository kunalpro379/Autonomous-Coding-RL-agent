package com.vpn.core;

import com.sun.jna.LastErrorException;
import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.IntByReference;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * JNA wrapper for Linux TUN device (/dev/net/tun).
 * Creates a virtual network interface and provides read/write of raw IP packets.
 */
public class TunDevice implements AutoCloseable {
    private static final String TUN_DEVICE = "/dev/net/tun";
    private static final short IFF_TUN = 0x0001;
    private static final short IFF_NO_PI = 0x1000;
    private int fd;
    private final String ifName;

    public TunDevice(String ifName) {
        this.ifName = ifName;
    }

    public void open() throws TunException {
        try {
            fd = CLib.INSTANCE.open(TUN_DEVICE, CLib.O_RDWR);
            if (fd < 0) {
                throw new TunException("Failed to open TUN device");
            }
            IfReq ifr = new IfReq();
            ifr.flags = IFF_TUN | IFF_NO_PI;
            ifr.ifrn_name = ifName;
            int err = CLib.INSTANCE.ioctl(fd, CLib.TUNSETIFF, ifr.getPointer());
            if (err < 0) {
                throw new TunException("ioctl TUNSETIFF failed");
            }
        } catch (LastErrorException e) {
            throw new TunException("Native error opening TUN: " + e.getMessage(), e);
        }
    }

    public int read(ByteBuffer buffer) throws IOException {
        int n = CLib.INSTANCE.read(fd, buffer, buffer.remaining());
        if (n < 0) {
            throw new IOException("TUN read error");
        }
        buffer.position(buffer.position() + n);
        return n;
    }

    public int write(ByteBuffer buffer) throws IOException {
        int n = CLib.INSTANCE.write(fd, buffer, buffer.position());
        if (n < 0) {
            throw new IOException("TUN write error");
        }
        buffer.position(buffer.position() + n);
        return n;
    }

    @Override
    public void close() {
        if (fd >= 0) {
            CLib.INSTANCE.close(fd);
            fd = -1;
        }
    }

    public String getIfName() {
        return ifName;
    }

    // JNA interface to C standard library
    private interface CLib extends Library {
        CLib INSTANCE = Native.load("c", CLib.class);
        int O_RDWR = 2;
        int TUNSETIFF = 0x400454ca;

        int open(String pathname, int flags) throws LastErrorException;
        int close(int fd) throws LastErrorException;
        int read(int fd, ByteBuffer buf, int count) throws LastErrorException;
        int write(int fd, ByteBuffer buf, int count) throws LastErrorException;
        int ioctl(int fd, int request, Pointer argp) throws LastErrorException;
    }

    // ifreq structure for ioctl
    private static class IfReq extends com.sun.jna.Structure {
        public String ifrn_name;
        public short flags;

        @Override
        protected java.util.List<String> getFieldOrder() {
            return java.util.Arrays.asList("ifrn_name", "flags");
        }
    }
}
