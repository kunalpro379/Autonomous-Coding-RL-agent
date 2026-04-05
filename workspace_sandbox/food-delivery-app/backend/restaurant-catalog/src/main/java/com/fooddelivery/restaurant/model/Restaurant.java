package com.fooddelivery.restaurant.model;

import jakarta.persistence.*;
import lombok.Data;
import java.util.ArrayList;
import java.util.List;

@Entity
@Data
public class Restaurant {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String name;
    
    private String description;
    private String address;
    private String phone;
    private String imageUrl;
    private Double rating;
    private Integer deliveryTime;
    private Double deliveryFee;
    
    @Column(name = "owner_id")
    private Long ownerId;
    
    @OneToMany(mappedBy = "restaurant", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<MenuItem> menuItems = new ArrayList<>();
    
    @Version
    private Long version;
}
