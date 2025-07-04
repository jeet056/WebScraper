package com.example.scraper;


public class Company {

    private String name;
    private String url;
    private String email;

    public Company(String name, String url, String email) {
        this.name = name;
        this.url = url;
        this.email = email;
    }

    public String getName() {
        return name;
    }
    public String getUrl() {
        return url;
    }
    public String getEmail() {
        return email;
    }

    public void setName(String name) {
        this.name = name;
    }
    public void setUrl(String url) {
        this.url = url;
    }
    public void setEmail(String email) {
        this.email = email;
    }

}
