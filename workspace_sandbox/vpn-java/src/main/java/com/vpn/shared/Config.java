package com.vpn.shared;

import java.net.InetSocketAddress;

public class Config {
    private InetSocketAddress serverAddress;
    private String tunDeviceName;
    private String sharedSecret;
    private int mtu = 1500;

    public InetSocketAddress getServerAddress() {
        return serverAddress;
    }

    public void setServerAddress(InetSocketAddress serverAddress) {
        this.serverAddress = serverAddress;
    }

    public String getTunDeviceName() {
        return tunDeviceName;
    }

    public void setTunDeviceName(String tunDeviceName) {
        this.tunDeviceName = tunDeviceName;
    }

    public String getSharedSecret() {
        return sharedSecret;
    }

    public void setSharedSecret(String sharedSecret) {
        this.sharedSecret = sharedSecret;
    }

    public int getMtu() {
        return mtu;
    }

    public void setMtu(int mtu) {
        this.mtu = mtu;
    }
}
