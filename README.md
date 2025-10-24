## Auto_Image-Spider

[Project Link](https://github.com/fuaneng/Auto_Image-Spider)
[![GitHub stars](https://img.shields.io/github/stars/fuaneng/Auto_Image-Spider?style=social)](https://github.com/fuaneng/Auto_Image-Spider/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/fuaneng/Auto_Image-Spider?style=social)](https://github.com/fuaneng/Auto_Image-Spider/network/members)

---

## 🏷 Topics

`Image Crawler` | `Selenium` | `Requests` | `Scrapy` | `DrissionPage` | `Redis` | `Python` | `Batch Image Collection` | `AIGC Training Dataset`

![liblib Personal Page](https://liblibai-online.liblib.cloud/img/db14e0c0ab354c569a27c03b25b2aff8/cd6a410fefc4b09e7b56c3bdca810809bcde70e07d3c6aa04b1829af2980ad89.png)

---

## 📢 Project Overview

This project is a **Python-based image crawling toolkit** designed for **batch downloading of image resources**.
It supports multiple stock photo and image sites, keyword-based batch crawling, automatic image saving, and CSV logging.
It’s ideal for **image dataset collection** or **AIGC (AI-generated content) training material preparation**.
Please use it responsibly to avoid overloading target websites.

---

## 📋 Introduction

* This project is maintained by the author and aims to collect images, titles, and original URLs from various image/resource websites as AIGC training data.
* Supports multiple target websites (see section **“Supported Sites & Framework Mapping”** below).
* Core features include: automated browser simulation, scrolling and “load more” handling, pagination, static requests, deduplication, and CSV + image saving.
* Scripts can execute in batch mode using a tag file (one keyword per line).
* Output includes fields like Title, Image Filename, Original URL, and Search Keyword.

---

## 🛠 Tech Stack & Framework Overview

* **Language:** Python 3.x
* Common libraries/tools:

  * `selenium`: Browser automation for scrolling, button clicks, and dynamic content retrieval.
  * `requests` / `urllib`: For static requests and direct image downloading.
  * `scrapy`: For structured crawlers and link discovery with pagination support.
  * `DrissionPage`: A modern Python browser automation/rendering library (can replace or complement Selenium).
  * `redis`: Optional, for URL deduplication, caching, and status tracking.
  * File system libraries (`os`, `pathlib`, etc.) for directory and image management.
* Each script chooses an appropriate method (static request, browser simulation, pagination, etc.) based on target site characteristics.

---

## ✅ Supported Sites & Framework Mapping (Partial)

Below is a partial list of supported or planned sites, with key crawling features and the suggested framework/method.

| Directory / Script Name | Target Website | Crawling Features                                      | Framework / Method Used               | Notes                     |
| ----------------------- | -------------- | ------------------------------------------------------ | ------------------------------------- | ------------------------- |
| `Lifeofpix/`            | Life of Pix    | Static pagination, no login required, direct downloads | `requests` + static HTML parsing      | Simple scenario           |
| `Unsplash/`             | Unsplash       | Infinite scroll or pagination API, dynamic content     | `selenium` or `requests` pagination   | Browser optional          |
| `FreePhotos_cc/`        | FreePhotos.cc  | Free stock photos, many pages                          | `requests` + `BeautifulSoup` / `lxml` | Static requests preferred |
| `ArtStation/`           | ArtStation     | Digital art site, complex dynamic loading              | `selenium` + ChromeDriver             | Dynamic “load more”       |
| `Civitai/`              | Civitai        | Model + image resources, requires login or cookies     | `selenium` + login handler            | Login + scroll/pagination |
| …(other directories)    | (to be added)  | (to be added)                                          | (to be added)                         | (remarks)                 |

> ⚠️ **Note:** This table is for reference.
> Please verify each script’s actual imports (e.g. `import drissionpage`, `import scrapy`, `from selenium import webdriver`, etc.) to confirm the used framework.

---

## 📂 Project Structure & Configuration

* `tag_file_path`: Path to tag file (e.g. `tags.txt`), one keyword per line.
* `save_path_all`: Root save directory (auto-created if not existing).
* Script naming convention: `crawl_lifeofpix.py`, `crawl_unsplash.py`, etc.
* Before running, specify configuration in script header or config file:

  * Tag file path, save directory, ChromeDriver path, whether to enable Redis, etc.
* **Output files:**

  * CSV file (e.g. `all_records.csv`) including:

    * `Title` – Image title
    * `ImageName` – Saved filename
    * `URL` – Original image link
    * `TAG` – Search keyword
  * Images saved in structure: `save_path_all/<site_name>/<tag>/…`

---

## ▶️ Quick Start Guide

1. Install Python 3 (recommended ≥3.8).
2. Install dependencies:

   ```bash
   pip install selenium redis beautifulsoup4 lxml requests drissionpage scrapy
   ```
3. Download a ChromeDriver matching your local Chrome version and configure the path in the script:

   ```bash
   # Recommended fixed path to avoid environment variable issues
   CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
   ```
4. *(Optional)* If using Redis deduplication, start Redis (default host=localhost, port=6379, db=0).
5. Prepare your tag file (e.g. `tags.txt`), one keyword per line.
6. Run a specific crawler script, for example:

   ```bash
   python crawl_lifeofpix.py --tag_file tags.txt --save_dir ./images/lifeofpix
   ```
7. Wait for execution to finish, then check your output directory and CSV log.

---

## ⚠️ Notes & Recommendations

* Many target sites have **anti-scraping mechanisms** (e.g. IP limits, JS rendering, infinite scrolling, CAPTCHA). Recommended practices:

  * Control crawl rate with random delays (`time.sleep()`).
  * Use proxy pools or rotating IPs if necessary.
  * Avoid high concurrency that may trigger bans.
* When using Selenium, ensure **ChromeDriver** matches your **Chrome browser version**; otherwise automation may fail.
* You can disable or modify Redis-related logic if deduplication isn’t required.
* Ensure downloaded images are used legally — comply with the target site’s copyright or license terms, and use only for research or non-commercial purposes.
* If the script fails or stops unexpectedly, check:

  * Network stability
  * Browser driver path
  * Tag file format
  * Target page structure changes

---

## 🧩 Contribution & License

This project is open-sourced under the **MIT License** — contributions are welcome!

You’re encouraged to:

* Submit issues for bugs or feature requests
* Fork the repository and add or improve crawlers (support more sites, optimize performance, enhance deduplication, etc.)
* Share your ideas and suggestions
* Respect target site ToS / copyright terms — for **legal and ethical use only**

---
