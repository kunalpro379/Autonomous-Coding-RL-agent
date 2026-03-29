package com.vpn.client;

import com.vpn.core.tun.TunDevice;
import com.vpn.core.crypto.CipherEngine;
import com.vpn.core.protocol.TunnelProtocol;
import com.vpn.shared.Config;
import com.vpn.shared.VpnException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.Socket;

public class VpnClient {
    private static final Logger LOG = LoggerFactory.getLogger(VpnClient.class);

    private final Config config;
    private TunDevice tunDevice;
    private Socket tunnelSocket;
    private CipherEngine cipherEngine;
    private volatile boolean running;

    public VpnClient(Config config) {
        this.config = config;
    }

    public void start() {
        try {
            LOG.info("Starting VPN client to {}", config.getServerAddress());
            tunDevice = new TunDevice(config.getTunDeviceName(), config.getMtu());
            tunDevice.open();

            tunnelSocket = new Socket();
            tunnelSocket.connect(config.getServerAddress());

            cipherEngine = new CipherEngine(config.getSharedSecret());

            running = true;
            new Thread(this::tunToTunnelLoop, "tun-reader").start();
            new Thread(this::tunnelToTunLoop, "tunnel-reader").start();

            LOG.info("VPN client started");
        } catch (Exception e) {
            throw new VpnException("Failed to start VPN client", e);
        }
    }

    private void tunToTunnelLoop() {
        try {
            while (running) {
                byte[] packet = tunDevice.readPacket();
                if (packet == null) continue;
                byte[] encrypted = cipherEngine.encrypt(packet);
                TunnelProtocol.sendPacket(tunnelSocket, encrypted);
            }
        } catch (IOException e) {
            if (running) {
                LOG.error("Error reading from TUN or sending to tunnel", e);
                stop();
            }
        }
    }

    private void tunnelToTunLoop() {
        try {
            while (running) {
                byte[] encrypted = TunnelProtocol.receivePacket(tunnelSocket);
                byte[] decrypted = cipherEngine.decrypt(encrypted);
                tunDevice.writePacket(decrypted);
            }
        } catch (IOException e) {
            if (running) {
                LOG.error("Error reading from tunnel or writing to TUN", e);
                stop();
            }
        }
    }

    public void stop() {
        running = false;
        try {
            if (tunnelSocket != null) tunnelSocket.close();
        } catch (IOException e) {
            LOG.warn("Error closing tunnel socket", e);
        }
        try {
            if (tunDevice != null) tunDevice.close();
        } catch (IOException e) {
            LOG.warn("Error closing TUN device", e);
        }
        LOG.info("VPN client stopped");
    }

    public static void main(String[] args) {
        Config config = new Config();
        config.setServerAddress(new java.net.InetSocketAddress("127.0.0.1", 5555));
        config.setTunDeviceName("tun0");
        config.setSharedSecret("AAECAwQFBgcICQoLDA0ODxAREhM=");

        VpnClient client = new VpnClient(config);
        client.start();

        Runtime.getRuntime().addShutdownHook(new Thread(client::stop));
    }
}
