package com.vpn.core;

public class TunException extends Exception {
    public TunException(String message) {
        super(message);
    }

    public TunException(String message, Throwable cause) {
        super(message, cause);
    }
}
