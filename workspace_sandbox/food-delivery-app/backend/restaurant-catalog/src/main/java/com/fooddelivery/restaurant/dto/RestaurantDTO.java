package com.fooddelivery.restaurant.dto;

import lombok.Data;

@Data
public class RestaurantDTO {
    private Long id;
    private String name;
    private String description;
    private String address;
    private String phone;
    private String imageUrl;
    private Double rating;
    private Integer deliveryTime;
    private Double deliveryFee;
    private Long ownerId;
}
