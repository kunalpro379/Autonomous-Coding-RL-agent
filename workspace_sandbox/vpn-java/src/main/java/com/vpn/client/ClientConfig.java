package com.vpn.client;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.io.IOException;

public class ClientConfig {
    private String serverHost;
    private int serverPort;
    private String tunName;
    private String tunIp;
    private String tunNetmask;
    private String sharedSecret;

    // Jackson needs default constructor
    public ClientConfig() {}

    public String getServerHost() { return serverHost; }
    public void setServerHost(String serverHost) { this.serverHost = serverHost; }

    public int getServerPort() { return serverPort; }
    public void setServerPort(int serverPort) { this.serverPort = serverPort; }

    public String getTunName() { return tunName; }
    public void setTunName(String tunName) { this.tunName = tunName; }

    public String getTunIp() { return tunIp; }
    public void setTunIp(String tunIp) { this.tunIp = tunIp; }

    public String getTunNetmask() { return tunNetmask; }
    public void setTunNetmask(String tunNetmask) { this.tunNetmask = tunNetmask; }

    public String getSharedSecret() { return sharedSecret; }
    public void setSharedSecret(String sharedSecret) { this.sharedSecret = sharedSecret; }

    public static ClientConfig load(String path) throws IOException {
        ObjectMapper mapper = new ObjectMapper();
        return mapper.readValue(new File(path), ClientConfig.class);
    }
}
