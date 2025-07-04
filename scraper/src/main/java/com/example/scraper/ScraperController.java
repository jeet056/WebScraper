package com.example.scraper;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.http.HttpStatus;

import java.util.List;

@RestController
public class ScraperController {
    private final ScraperService scraperService;

    public ScraperController(ScraperService scraperService) {
        this.scraperService = scraperService;
    }

    @GetMapping("/api/scrape-js")
    public ResponseEntity<List<Company>> scrapeJs(@RequestParam String url) {
        try {
            List<Company> companies = scraperService.scrapeJs(url);
            return ResponseEntity.ok(companies);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}