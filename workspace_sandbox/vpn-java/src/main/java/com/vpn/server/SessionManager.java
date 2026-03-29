package com.vpn.server;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class SessionManager {
    private final Map<String, ClientSession> sessions = new ConcurrentHashMap<>();

    public void addSession(String clientId, ClientSession session) {
        sessions.put(clientId, session);
    }

    public ClientSession getSession(String clientId) {
        return sessions.get(clientId);
    }

    public void removeSession(String clientId) {
        sessions.remove(clientId);
    }

    public int getSessionCount() {
        return sessions.size();
    }
}
