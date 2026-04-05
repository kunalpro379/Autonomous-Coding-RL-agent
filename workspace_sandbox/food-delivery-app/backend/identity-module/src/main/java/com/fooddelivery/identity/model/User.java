package com.fooddelivery.identity.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
@Data
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String email;
    
    @Column(nullable = false)
    private String password;
    
    private String firstName;
    private String lastName;
    private String phone;
    private String address;
    
    @Enumerated(EnumType.STRING)
    private UserRole role = UserRole.CUSTOMER;
    
    private LocalDateTime createdAt;
    
    @Version
    private Long version;
    
    public enum UserRole {
        CUSTOMER, RESTAURANT_OWNER, ADMIN, DELIVERY_PERSON
    }
}
