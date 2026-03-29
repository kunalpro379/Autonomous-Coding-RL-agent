package com.vpn.common;

public class VPNException extends RuntimeException {
    public VPNException(String message) {
        super(message);
    }

    public VPNException(String message, Throwable cause) {
        super(message, cause);
    }
}
