package com.example.scraper;

import io.github.bonigarcia.wdm.WebDriverManager;
import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.*;

import org.springframework.stereotype.Service;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@Service
public class ScraperService {

    private WebDriver createDriver() {
        WebDriverManager.chromedriver().setup();
        ChromeOptions opts = new ChromeOptions();
        opts.addArguments("--headless", "--disable-gpu");
        return new ChromeDriver(opts);
    }

    public List<Company> scrapeJs(String url) {
        WebDriver driver = createDriver();
        driver.get(url);

        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(10));
        wait.until(ExpectedConditions.presenceOfElementLocated(By.cssSelector(".company-card")));

        List<WebElement> cards = driver.findElements(By.cssSelector(".company-card"));
        List<Company> out = new ArrayList<>();
        for (WebElement card : cards) {
            String name = card.findElement(By.cssSelector(".company-name")).getText();
            String website = card.findElement(By.cssSelector("a.website")).getDomAttribute("href");

            String email = "";
            try {
                WebElement emailEl = new WebDriverWait(driver, Duration.ofSeconds(3))
                    .until(ExpectedConditions.presenceOfNestedElementLocatedBy(
                        card, By.cssSelector("a[href^='mailto:']")));
                email = emailEl.getDomAttribute("href").replace("mailto:", "");
            } catch (TimeoutException ignored) { }

            out.add(new Company(name, url, email));
        }

        driver.quit();
        return out;
    }
}
