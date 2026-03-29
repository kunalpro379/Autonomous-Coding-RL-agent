package com.vpn.core.tunnel;

import com.vpn.common.VPNException;

public class TunException extends VPNException {
    public TunException(String message) {
        super(message);
    }

    public TunException(String message, Throwable cause) {
        super(message, cause);
    }
}
