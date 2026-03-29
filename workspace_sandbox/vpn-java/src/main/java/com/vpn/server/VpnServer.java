package com.vpn.server;

import com.vpn.core.crypto.CipherEngine;
import com.vpn.core.protocol.TunnelProtocol;
import com.vpn.shared.Config;
import com.vpn.shared.VpnException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class VpnServer {
    private static final Logger LOG = LoggerFactory.getLogger(VpnServer.class);

    private final Config config;
    private ServerSocket serverSocket;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private volatile boolean running;

    public VpnServer(Config config) {
        this.config = config;
    }

    public void start() {
        try {
            serverSocket = new ServerSocket(config.getServerAddress().getPort());
            running = true;
            LOG.info("VPN server listening on {}", config.getServerAddress());

            while (running) {
                Socket clientSocket = serverSocket.accept();
                LOG.info("New client connected from {}", clientSocket.getRemoteSocketAddress());
                executor.submit(() -> handleClient(clientSocket));
            }
        } catch (IOException e) {
            throw new VpnException("Failed to start VPN server", e);
        }
    }
