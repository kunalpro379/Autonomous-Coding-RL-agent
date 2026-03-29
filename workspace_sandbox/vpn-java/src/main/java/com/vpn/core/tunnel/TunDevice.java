package com.vpn.core.tunnel;

import com.sun.jna.LastErrorException;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.IntByReference;
import com.vpn.common.Constants;
import com.vpn.common.VPNException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Closeable;
import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

/**
 * Platform‑specific TUN device wrapper using JNA.
 * Currently implements Linux /dev/net/tun; Windows would need tap‑windows adapter.
 */
public class TunDevice implements Closeable {
    private static final Logger LOG = LoggerFactory.getLogger(TunDevice.class);
    private static final String TUN_DEVICE_PATH = "/dev/net/tun";
    private static final short IFF_TUN = 0x0001;
    private static final short IFF_NO_PI = 0x1000;
    private static final int TUNSETIFF = 0x400454CA;

    private final String name;
    private final int fd;
    private final FileChannel channel;

    static {
        // Load libc for ioctl
        Native.register("c");
    }

    // JNA native declarations
    private static native int open(String pathname, int flags) throws LastErrorException;
    private static native int ioctl(int fd, int request, Pointer arg) throws LastErrorException;
    private static native int close(int fd) throws LastErrorException;

    public TunDevice(String name) {
        this.name = name;
        try {
            fd = open(TUN_DEVICE_PATH, 0); // O_RDWR
            LOG.debug("Opened TUN device fd={}", fd);
            // Prepare ifreq structure
            byte[] ifreq = new byte[40]; // sizeof(struct ifreq)
            byte[] nameBytes = name.getBytes();
            System.arraycopy(nameBytes, 0, ifreq, 0, Math.min(nameBytes.length, 16));
            // Set flags: IFF_TUN | IFF_NO_PI
            short flags = IFF_TUN | IFF_NO_PI;
            ifreq[16] = (byte) (flags & 0xFF);
            ifreq[17] = (byte) ((flags >> 8) & 0xFF);
            Pointer ptr = new Pointer(Native.malloc(ifreq.length));
            ptr.write(0, ifreq, 0, ifreq.length);
            ioctl(fd, TUNSETIFF, ptr);
            Native.free(Pointer.nativeValue(ptr));
            LOG.info("TUN device {} created", name);
            // Open FileChannel for reading/writing
            channel = FileChannel.open(Paths.get(TUN_DEVICE_PATH), StandardOpenOption.READ, StandardOpenOption.WRITE);
        } catch (LastErrorException e) {
            throw new VPNException("Failed to create TUN device: " + e.getMessage(), e);
        } catch (IOException e) {
            throw new VPNException("Failed to open channel for TUN device", e);
        }
    }

    public static TunDevice createDefault() {
        String name = String.format(Constants.TUN_DEVICE_NAME, 0);
        return new TunDevice(name);
    }

    public byte[] readPacket() throws IOException {
        ByteBuffer buffer = ByteBuffer.allocateDirect(Constants.TUN_MTU);
        int read = channel.read(buffer);
        if (read <= 0) {
            return null;
        }
        buffer.flip();
        byte[] packet = new byte[read];
        buffer.get(packet);
        return packet;
    }

    public void writePacket(byte[] packet) throws IOException {
        ByteBuffer buffer = ByteBuffer.wrap(packet);
        channel.write(buffer);
    }

    public void setIpAddress(String ip, String netmask) {
        // Platform‑specific IP configuration would go here (e.g., calling `ip addr add` via ProcessBuilder)
        LOG.warn("IP address configuration not implemented; you must manually set IP {} on interface {}", ip, name);
    }

    @Override
    public void close() throws IOException {
        try {
            channel.close();
            close(fd);
            LOG.info("TUN device {} closed", name);
        } catch (LastErrorException e) {
            throw new IOException("Failed to close TUN device", e);
        }
    }
}
