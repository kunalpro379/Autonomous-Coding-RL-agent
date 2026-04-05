package com.fooddelivery.identity.dto;

import lombok.Data;

@Data
public class AuthResponse {
    private String token;
    private String email;
    private String firstName;
    private String lastName;
    private String role;
    
    public AuthResponse(String token, String email, String firstName, String lastName, String role) {
        this.token = token;
        this.email = email;
        this.firstName = firstName;
        this.lastName = lastName;
        this.role = role;
    }
}
