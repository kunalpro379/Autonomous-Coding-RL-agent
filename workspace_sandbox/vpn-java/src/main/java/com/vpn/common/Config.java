package com.vpn.common;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

public class Config {
    private final Properties props;

    public Config(String filePath) throws IOException {
        props = new Properties();
        try (FileInputStream fis = new FileInputStream(filePath)) {
            props.load(fis);
        }
    }

    public String getServerHost() {
        return props.getProperty("server.host", "localhost");
    }

    public int getServerPort() {
        return Integer.parseInt(props.getProperty("server.port", String.valueOf(Constants.DEFAULT_PORT)));
    }

    public String getSharedSecret() {
        return props.getProperty("shared.secret", "change-this-secret");
    }

    public boolean isServer() {
        return Boolean.parseBoolean(props.getProperty("mode.server", "false"));
    }
}
