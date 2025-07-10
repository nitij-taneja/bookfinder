import requests
from bs4 import BeautifulSoup
import json
import os

def search_aco(query, max_results=10):
    """
    Enhanced Arabic Collections Online (ACO) search with improved error handling and parsing
    """
    try:
        # Construct search URL with proper encoding
        search_url = f"https://dlib.nyu.edu/aco/search/?q={query}&scope=containsAny"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = []
        
        # Try multiple selectors for different page layouts
        book_containers = (
            soup.find_all("div", class_="item-details") or
            soup.find_all("div", class_="search-result") or
            soup.find_all("div", class_="result-item") or
            soup.find_all("article", class_="item")
        )
        
        for container in book_containers[:max_results]:
            try:
                # Try multiple selectors for title
                title_tag = (
                    container.find("h3", class_="item-title") or
                    container.find("h2", class_="title") or
                    container.find("a", class_="title") or
                    container.find("h3") or
                    container.find("h2")
                )
                
                # Try multiple selectors for author
                author_tag = (
                    container.find("p", class_="item-author") or
                    container.find("div", class_="author") or
                    container.find("span", class_="author") or
                    container.find("p", class_="author")
                )
                
                title = title_tag.get_text(strip=True) if title_tag else "N/A"
                author = author_tag.get_text(strip=True) if author_tag else "N/A"
                
                # Clean up title and author
                title = title.replace("Title:", "").strip()
                author = author.replace("Author:", "").replace("المؤلف:", "").strip()
                
                pdf_links = []
                
                # Look for PDF download links with various patterns
                pdf_link_selectors = [
                    "a[href*='.pdf']",
                    "a[href*='download']",
                    "a.download-link",
                    "a[title*='PDF']",
                    "a[title*='تحميل']"
                ]
                
                for selector in pdf_link_selectors:
                    links = container.select(selector)
                    for link in links:
                        href = link.get("href")
                        if href:
                            # Make absolute URL if relative
                            if href.startswith("/"):
                                href = "https://dlib.nyu.edu" + href
                            elif not href.startswith("http"):
                                href = "https://dlib.nyu.edu/aco/" + href
                            
                            link_text = link.get_text(strip=True).lower()
                            if "low" in link_text or "منخفضة" in link_text:
                                pdf_links.append({"type": "low_res_pdf", "url": href})
                            elif "high" in link_text or "عالية" in link_text:
                                pdf_links.append({"type": "high_res_pdf", "url": href})
                            else:
                                pdf_links.append({"type": "pdf", "url": href})
                
                # Only add results that have at least a title and some content
                if title and title != "N/A" and len(title) > 2:
                    results.append({
                        "title": title,
                        "author": author,
                        "pdf_links": pdf_links,
                        "source": "aco"
                    })
                    
            except Exception as e:
                print(f"Error parsing ACO result container: {e}")
                continue
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching ACO: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during ACO search: {e}")
        return []

def search_rapidapi_arabic_books(query, max_results=10):
    """
    Search Arabic books using RapidAPI Arabic Books Library
    """
    try:
        # Note: In production, this should be an environment variable
        rapidapi_key = os.environ.get("RAPIDAPI_KEY", "")
        
        if not rapidapi_key:
            print("RapidAPI key not found, skipping RapidAPI Arabic Books search")
            return []
        
        url = "https://arabic-books-library.p.rapidapi.com/search"
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "arabic-books-library.p.rapidapi.com"
        }
        
        params = {"title": query}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        # Parse the response based on the API structure
        books = data.get("books", []) if isinstance(data, dict) else data
        
        for book in books[:max_results]:
            try:
                title = book.get("title", "N/A")
                author = book.get("author", "N/A")
                category = book.get("category", "")
                description = book.get("description", "")
                
                # Look for download links
                pdf_links = []
                download_url = book.get("download_url") or book.get("pdf_url") or book.get("url")
                
                if download_url:
                    pdf_links.append({"type": "pdf", "url": download_url})
                
                results.append({
                    "title": title,
                    "author": author,
                    "category": category,
                    "description": description,
                    "pdf_links": pdf_links,
                    "source": "rapidapi_arabic_books"
                })
                
            except Exception as e:
                print(f"Error parsing RapidAPI book result: {e}")
                continue
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching RapidAPI Arabic Books: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during RapidAPI search: {e}")
        return []

def search_noor_library(query, max_results=10):
    """
    Search Noor Library for Arabic books (web scraping approach)
    """
    try:
        # Noor Library search URL
        search_url = "https://www.noor-book.com/en/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        params = {"q": query}
        
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = []
        
        # Look for book containers
        book_containers = (
            soup.find_all("div", class_="book-item") or
            soup.find_all("div", class_="book") or
            soup.find_all("article", class_="book") or
            soup.find_all("div", class_="result")
        )
        
        for container in book_containers[:max_results]:
            try:
                # Extract title
                title_tag = (
                    container.find("h3") or
                    container.find("h2") or
                    container.find("a", class_="title") or
                    container.find("div", class_="title")
                )
                
                # Extract author
                author_tag = (
                    container.find("div", class_="author") or
                    container.find("span", class_="author") or
                    container.find("p", class_="author")
                )
                
                title = title_tag.get_text(strip=True) if title_tag else "N/A"
                author = author_tag.get_text(strip=True) if author_tag else "N/A"
                
                # Look for download links
                pdf_links = []
                download_links = container.find_all("a", href=True)
                
                for link in download_links:
                    href = link.get("href")
                    link_text = link.get_text(strip=True).lower()
                    
                    if any(keyword in link_text for keyword in ["download", "تحميل", "pdf"]):
                        if href.startswith("/"):
                            href = "https://www.noor-book.com" + href
                        pdf_links.append({"type": "pdf", "url": href})
                
                if title and title != "N/A":
                    results.append({
                        "title": title,
                        "author": author,
                        "pdf_links": pdf_links,
                        "source": "noor_library"
                    })
                    
            except Exception as e:
                print(f"Error parsing Noor Library result: {e}")
                continue
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching Noor Library: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during Noor Library search: {e}")
        return []

def search_project_gutenberg_arabic(query, max_results=10):
    """
    Search Project Gutenberg for Arabic books
    """
    try:
        # Project Gutenberg API for Arabic books
        url = "https://gutendx.com/books"
        params = {
            "search": query,
            "languages": "ar",
            "mime_type": "application/pdf"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        for book in data.get("results", [])[:max_results]:
            try:
                title = book.get("title", "N/A")
                authors = book.get("authors", [])
                author = ", ".join([a.get("name", "") for a in authors]) if authors else "N/A"
                
                # Get PDF download link
                formats = book.get("formats", {})
                pdf_url = formats.get("application/pdf")
                
                pdf_links = []
                if pdf_url:
                    pdf_links.append({"type": "pdf", "url": pdf_url})
                
                results.append({
                    "title": title,
                    "author": author,
                    "pdf_links": pdf_links,
                    "source": "project_gutenberg_arabic"
                })
                
            except Exception as e:
                print(f"Error parsing Project Gutenberg result: {e}")
                continue
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching Project Gutenberg Arabic: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during Project Gutenberg search: {e}")
        return []

def enhanced_arabic_search(query, sources=None, max_results_per_source=5):
    """
    Enhanced Arabic book search that combines multiple sources
    """
    if sources is None:
        sources = ["aco", "rapidapi", "noor", "gutenberg"]
    
    all_results = []
    
    # Search each source
    for source in sources:
        try:
            if source == "aco":
                results = search_aco(query, max_results_per_source)
                all_results.extend(results)
            elif source == "rapidapi":
                results = search_rapidapi_arabic_books(query, max_results_per_source)
                all_results.extend(results)
            elif source == "noor":
                results = search_noor_library(query, max_results_per_source)
                all_results.extend(results)
            elif source == "gutenberg":
                results = search_project_gutenberg_arabic(query, max_results_per_source)
                all_results.extend(results)
        except Exception as e:
            print(f"Error searching source {source}: {e}")
            continue
    
    # Remove duplicates based on title similarity
    unique_results = []
    seen_titles = set()
    
    for result in all_results:
        title_key = result["title"].lower().strip()
        if title_key not in seen_titles and len(title_key) > 2:
            seen_titles.add(title_key)
            unique_results.append(result)
    
    return unique_results

# Backward compatibility - keep the original function name
def search_aco_legacy(query):
    """Legacy function for backward compatibility"""
    return search_aco(query)

# Example usage and testing
if __name__ == "__main__":
    # Test the enhanced search
    test_query = "أليس في بلاد العجائب"
    print(f"Testing enhanced Arabic search for: {test_query}")
    
    results = enhanced_arabic_search(test_query)
    
    for i, book in enumerate(results, 1):
        print(f"\n{i}. Title: {book.get('title')}")
        print(f"   Author: {book.get('author')}")
        print(f"   Source: {book.get('source')}")
        for pdf in book.get('pdf_links', []):
            print(f"   PDF ({pdf.get('type')}): {pdf.get('url')}")
        print("---")

