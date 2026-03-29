package com.vpn.server;

import com.vpn.crypto.CipherEngine;
import com.vpn.common.FrameCodec;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.ByteBuffer;

/**
 * Handles a single connected VPN client.
 */
public class ClientSession implements Runnable {
    private static final Logger LOG = LoggerFactory.getLogger(ClientSession.class);
    private final Socket socket;
    private final CipherEngine cipher;
    private volatile boolean running = true;

    public ClientSession(Socket socket, byte[] sharedSecret) {
        this.socket = socket;
        this.cipher = new CipherEngine(sharedSecret);
    }

    @Override
    public void run() {
        try (InputStream in = socket.getInputStream();
             OutputStream out = socket.getOutputStream()) {
            LOG.info("Client session started: {}", socket.getRemoteSocketAddress());
            byte[] hello = new byte[5];
            int read = in.read(hello);
            if (read != 5 || !"HELLO".equals(new String(hello))) {
                LOG.warn("Invalid handshake from client");
                return;
            }
