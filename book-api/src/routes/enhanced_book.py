import requests
import os
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from epub2pdf import EpubPdfConverter
import json

from src.routes.llm import extract_book_info, intelligent_search_planning, enhance_search_results, localize_book_categories, quick_translate_categories
from src.routes.arabic_books import search_aco, enhanced_arabic_search

enhanced_book_bp = Blueprint("enhanced_book", __name__)

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
GUTENDX_API = "https://gutendx.com/books"

# Helper function to get PDF URL from Google Books API response
def get_google_books_pdf_url(access_info):
    if access_info and access_info.get("viewability") == "FULL" and access_info.get("pdf") and access_info["pdf"].get("isAvailable"):
        return access_info["pdf"].get("acsTokenLink") or access_info["pdf"].get("downloadLink")
    return None

# Helper function to get PDF URL from Gutendx API response
def get_gutendx_pdf_url(formats):
    if formats:
        # Prioritize application/pdf, then text/html, then text/plain
        if "application/pdf" in formats:
            return formats["application/pdf"]
        elif "text/html" in formats:
            return formats["text/html"]
        elif "text/plain" in formats:
            return formats["text/plain"]
    return None

# Helper function to get PDF URL from Internet Archive with multiple fallbacks
def get_internet_archive_pdf_url(identifier):
    """Get the actual PDF download URL by querying Internet Archive metadata with multiple fallbacks"""
    if not identifier:
        return None

    pdf_urls = []

    try:
        # Method 1: Query Internet Archive metadata API to get file list
        metadata_url = f"https://archive.org/metadata/{identifier}"
        response = requests.get(metadata_url, timeout=10)

        if response.ok:
            metadata = response.json()
            files = metadata.get("files", [])

            # Look for PDF files
            for file in files:
                file_name = file.get("name", "")
                file_format = file.get("format", "")

                # Check if it's a PDF file (either by extension or format)
                if (file_name.lower().endswith('.pdf') or
                    file_format.lower() in ['pdf', 'text pdf']):
                    pdf_url = f"https://archive.org/download/{identifier}/{file_name}"
                    pdf_urls.append(pdf_url)

            # If we found PDFs, return the first one
            if pdf_urls:
                return pdf_urls[0]

    except Exception as e:
        print(f"Error getting PDF URL from metadata for {identifier}: {e}")

    # Method 2: Try common PDF filename patterns
    fallback_patterns = [
        f"{identifier}.pdf",
        f"{identifier.replace('-', ' ')}.pdf",
        f"{identifier.replace('-', '_')}.pdf",
        f"{identifier.title().replace('-', ' ')}.pdf",
        f"{identifier.upper()}.pdf",
        f"{identifier.lower()}.pdf"
    ]

    for pattern in fallback_patterns:
        try:
            test_url = f"https://archive.org/download/{identifier}/{pattern}"
            # Quick HEAD request to check if file exists
            head_response = requests.head(test_url, timeout=5)
            if head_response.status_code == 200:
                return test_url
        except:
            continue

    # Method 3: Return the most likely URL even if we can't verify it
    return f"https://archive.org/download/{identifier}/{identifier}.pdf"

def search_google_books(search_terms, language="en", author=None):
    """Search Google Books with intelligent query construction"""
    try:
        # Construct search query
        query_parts = search_terms.copy()
        if author:
            query_parts.append(f"author:{author}")
        
        search_query = " ".join(query_parts)
        
        params = {
            "q": search_query,
            "langRestrict": language,
            "maxResults": 10
        }
        
        response = requests.get(GOOGLE_BOOKS_API, params=params)
        response.raise_for_status()
        data = response.json()
        
        books = []
        for item in data.get("items", []):
            volume_info = item.get("volumeInfo", {})
            access_info = item.get("accessInfo", {})
            
            title = volume_info.get("title")
            authors = volume_info.get("authors", [])
            categories = volume_info.get("categories", [])
            description = volume_info.get("description")
            image_links = volume_info.get("imageLinks", {})
            thumbnail = image_links.get("thumbnail")
            info_link = volume_info.get("infoLink")
            
            pdf_url = get_google_books_pdf_url(access_info)
            
            books.append({
                "title": title,
                "author": ", ".join(authors),
                "categories": categories,
                "description": description,
                "thumbnail": thumbnail,
                "info_link": info_link,
                "pdf_links": [{"source": "Google Books", "url": pdf_url}] if pdf_url else [],
                "source": "google_books"
            })
        
        return books
    except Exception as e:
        print(f"Error searching Google Books: {e}")
        return []

def search_gutendx(search_terms, language="en"):
    """Search Gutendx for public domain books"""
    try:
        search_query = " ".join(search_terms)
        params = {"search": search_query}
        
        response = requests.get(GUTENDX_API, params=params)
        response.raise_for_status()
        data = response.json()
        
        books = []
        for result in data.get("results", []):
            pdf_url = get_gutendx_pdf_url(result.get("formats"))
            
            if pdf_url:  # Only include books with available PDFs
                books.append({
                    "title": result.get("title"),
                    "author": ", ".join([author.get("name", "") for author in result.get("authors", [])]),
                    "categories": result.get("subjects", []),
                    "description": "",  # Gutendx doesn't provide descriptions
                    "thumbnail": None,  # Gutendx doesn't provide thumbnails directly
                    "info_link": result.get("formats", {}).get("text/html"),
                    "pdf_links": [{"source": "Gutendx", "url": pdf_url}],
                    "source": "gutendx"
                })
        
        return books
    except Exception as e:
        print(f"Error searching Gutendx: {e}")
        return []

def search_project_gutenberg(search_terms):
    """Search Project Gutenberg for free ebooks"""
    books = []
    try:
        search_query = " ".join(search_terms)
        # Project Gutenberg search API
        params = {
            "search": search_query,
            "format": "json"
        }

        response = requests.get("https://gutendx.com/books/", params=params, timeout=10)
        if response.ok:
            data = response.json()

            for book in data.get("results", [])[:10]:  # Limit to 10 results
                title = book.get("title", "")
                authors = book.get("authors", [])
                author = ", ".join([a.get("name", "") for a in authors]) if authors else ""
                subjects = book.get("subjects", [])

                # Get PDF download links
                formats = book.get("formats", {})
                pdf_links = []

                for format_key, url in formats.items():
                    if "pdf" in format_key.lower():
                        pdf_links.append({
                            "source": "Project Gutenberg",
                            "url": url
                        })

                if pdf_links:  # Only include books with PDF links
                    books.append({
                        "title": title,
                        "author": author,
                        "categories": subjects,
                        "description": f"Free ebook from Project Gutenberg. Subjects: {', '.join(subjects[:3])}",
                        "thumbnail": "",
                        "info_link": f"https://www.gutenberg.org/ebooks/{book.get('id', '')}",
                        "pdf_links": pdf_links,
                        "source": "project_gutenberg"
                    })

    except Exception as e:
        print(f"Project Gutenberg search failed: {e}")

    return books

def search_open_library(search_terms):
    """Search Open Library for books with available downloads"""
    books = []
    try:
        search_query = " ".join(search_terms)
        params = {
            "q": search_query,
            "format": "json",
            "limit": 10
        }

        response = requests.get("https://openlibrary.org/search.json", params=params, timeout=10)
        if response.ok:
            data = response.json()

            for doc in data.get("docs", []):
                title = doc.get("title", "")
                author_names = doc.get("author_name", [])
                author = ", ".join(author_names) if author_names else ""
                subjects = doc.get("subject", [])

                # Check if book has available formats
                ia_id = doc.get("ia", [])
                if ia_id:
                    # If it has Internet Archive ID, it might have downloadable formats
                    pdf_links = []
                    for archive_id in ia_id[:1]:  # Check first archive ID
                        pdf_url = get_internet_archive_pdf_url(archive_id)
                        if pdf_url:
                            pdf_links.append({
                                "source": "Open Library (Internet Archive)",
                                "url": pdf_url
                            })

                    if pdf_links:
                        books.append({
                            "title": title,
                            "author": author,
                            "categories": subjects[:5] if subjects else [],
                            "description": f"Available through Open Library. Subjects: {', '.join(subjects[:3]) if subjects else 'Various'}",
                            "thumbnail": f"https://covers.openlibrary.org/b/id/{doc.get('cover_i', '')}-M.jpg" if doc.get('cover_i') else "",
                            "info_link": f"https://openlibrary.org{doc.get('key', '')}",
                            "pdf_links": pdf_links,
                            "source": "open_library"
                        })

    except Exception as e:
        print(f"Open Library search failed: {e}")

    return books

def search_internet_archive_comprehensive(search_terms):
    """Comprehensive Internet Archive search with multiple strategies"""
    all_books = []
    search_query = " ".join(search_terms)

    # Strategy 1: Direct title search with PDF format
    try:
        params1 = {
            "q": f"title:({search_query}) AND mediatype:texts AND format:PDF",
            "fl": "identifier,title,creator,description,subject,downloads",
            "rows": 15,
            "sort": "downloads desc",
            "output": "json"
        }
        response1 = requests.get("https://archive.org/advancedsearch.php", params=params1, timeout=15)
        if response1.ok:
            data1 = response1.json()
            all_books.extend(parse_internet_archive_response(data1))
    except Exception as e:
        print(f"IA Strategy 1 failed: {e}")

    # Strategy 2: Broader search without strict title matching
    try:
        params2 = {
            "q": f"({search_query}) AND mediatype:texts AND format:PDF",
            "fl": "identifier,title,creator,description,subject,downloads",
            "rows": 10,
            "sort": "downloads desc",
            "output": "json"
        }
        response2 = requests.get("https://archive.org/advancedsearch.php", params=params2, timeout=15)
        if response2.ok:
            data2 = response2.json()
            all_books.extend(parse_internet_archive_response(data2))
    except Exception as e:
        print(f"IA Strategy 2 failed: {e}")

    # Strategy 3: Search for any text format, then filter for PDFs
    try:
        params3 = {
            "q": f"title:({search_query}) AND mediatype:texts",
            "fl": "identifier,title,creator,description,subject,downloads",
            "rows": 20,
            "sort": "downloads desc",
            "output": "json"
        }
        response3 = requests.get("https://archive.org/advancedsearch.php", params=params3, timeout=15)
        if response3.ok:
            data3 = response3.json()
            # Parse and filter for books that actually have PDFs
            potential_books = parse_internet_archive_response(data3)
            for book in potential_books:
                if book.get("pdf_links"):  # Only add if PDF links exist
                    all_books.append(book)
    except Exception as e:
        print(f"IA Strategy 3 failed: {e}")

    # Remove duplicates
    seen_identifiers = set()
    unique_books = []
    for book in all_books:
        identifier = book.get("info_link", "").split("/")[-1]
        if identifier not in seen_identifiers:
            seen_identifiers.add(identifier)
            unique_books.append(book)

    return unique_books

def parse_internet_archive_response(data):
    """Parse Internet Archive API response"""
    books = []
    for doc in data.get("response", {}).get("docs", []):
        identifier = doc.get("identifier")
        title = doc.get("title")
        creator = doc.get("creator", [])
        description = doc.get("description", "")
        subjects = doc.get("subject", [])

        if isinstance(creator, list):
            author = ", ".join(creator)
        else:
            author = creator or ""

        if isinstance(description, list):
            description = " ".join(description)

        if isinstance(subjects, list):
            categories = subjects
        else:
            categories = [subjects] if subjects else []

        pdf_url = get_internet_archive_pdf_url(identifier)

        books.append({
            "title": title,
            "author": author,
            "categories": categories,
            "description": description,
            "thumbnail": f"https://archive.org/services/img/{identifier}",
            "info_link": f"https://archive.org/details/{identifier}",
            "pdf_links": [{"source": "Internet Archive", "url": pdf_url}] if pdf_url else [],
            "source": "internet_archive"
        })

    return books

def search_internet_archive(search_terms):
    """Search Internet Archive for books with PDF downloads"""
    return search_internet_archive_comprehensive(search_terms)

def merge_duplicate_books(books):
    """Merge books with same title and author, combining their PDF links"""
    merged_books = {}
    
    for book in books:
        key = f"{book.get('title', '').lower()}_{book.get('author', '').lower()}"
        
        if key in merged_books:
            # Merge PDF links
            existing_sources = [link.get("source") for link in merged_books[key]["pdf_links"]]
            for pdf_link in book.get("pdf_links", []):
                if pdf_link.get("source") not in existing_sources:
                    merged_books[key]["pdf_links"].append(pdf_link)
            
            # Update other fields if they're empty in the existing book
            if not merged_books[key].get("description") and book.get("description"):
                merged_books[key]["description"] = book["description"]
            if not merged_books[key].get("thumbnail") and book.get("thumbnail"):
                merged_books[key]["thumbnail"] = book["thumbnail"]
            if not merged_books[key].get("categories") and book.get("categories"):
                merged_books[key]["categories"] = book["categories"]
        else:
            merged_books[key] = book.copy()
    
    return list(merged_books.values())

@enhanced_book_bp.route("/pdf-priority-search", methods=["POST"])
@cross_origin()
def pdf_priority_search():
    """
    PDF-First Book Search - Prioritizes finding downloadable PDFs from multiple sources
    """
    try:
        data = request.get_json()
        query = data.get("query")
        lang = data.get("lang", "en")

        if not query:
            return jsonify({"error": "Query is required"}), 400

        print(f"PDF-Priority search for: {query}")
        all_books = []
        search_terms = [query]

        # Step 1: Search Internet Archive (comprehensive search)
        print("Searching Internet Archive for PDFs...")
        try:
            ia_books = search_internet_archive_comprehensive(search_terms)
            all_books.extend(ia_books)
            print(f"Internet Archive found {len(ia_books)} books")
        except Exception as e:
            print(f"Internet Archive search failed: {e}")

        # Step 2: Search Project Gutenberg for public domain PDFs
        print("Searching Project Gutenberg for PDFs...")
        try:
            gutenberg_books = search_project_gutenberg(search_terms)
            all_books.extend(gutenberg_books)
            print(f"Project Gutenberg found {len(gutenberg_books)} books")
        except Exception as e:
            print(f"Project Gutenberg search failed: {e}")

        # Step 3: Search Open Library
        print("Searching Open Library for PDFs...")
        try:
            openlibrary_books = search_open_library(search_terms)
            all_books.extend(openlibrary_books)
            print(f"Open Library found {len(openlibrary_books)} books")
        except Exception as e:
            print(f"Open Library search failed: {e}")

        # Step 4: Search Gutendx as fallback
        print("Searching Gutendx for public domain PDFs...")
        try:
            gutendx_books = search_gutendx(search_terms, language=lang)
            all_books.extend(gutendx_books)
            print(f"Gutendx found {len(gutendx_books)} books")
        except Exception as e:
            print(f"Gutendx search failed: {e}")

        # Step 5: Search Google Books (for metadata, rarely has free PDFs)
        print("Searching Google Books for metadata...")
        try:
            google_books = search_google_books(search_terms, language=lang)
            all_books.extend(google_books)
            print(f"Google Books found {len(google_books)} books")
        except Exception as e:
            print(f"Google Books search failed: {e}")

        # Step 6: Merge and prioritize books with PDFs
        merged_books = merge_duplicate_books(all_books)

        # Sort by PDF availability (books with PDFs first)
        pdf_books = [book for book in merged_books if book.get("pdf_links")]
        non_pdf_books = [book for book in merged_books if not book.get("pdf_links")]

        # Further sort PDF books by source reliability
        source_priority = {
            "internet_archive": 1,
            "project_gutenberg": 2,
            "open_library": 3,
            "gutendx": 4,
            "google_books": 5
        }

        pdf_books.sort(key=lambda x: source_priority.get(x.get("source", ""), 99))

        final_results = pdf_books + non_pdf_books

        return jsonify({
            "results": final_results,
            "pdf_count": len(pdf_books),
            "total_count": len(final_results),
            "sources_searched": ["Internet Archive", "Project Gutenberg", "Open Library", "Gutendx", "Google Books"],
            "message": f"Found {len(pdf_books)} books with PDF downloads out of {len(final_results)} total results"
        })

    except Exception as e:
        print(f"Error in PDF priority search: {e}")
        return jsonify({"error": "Search failed"}), 500

@enhanced_book_bp.route("/enhanced-search", methods=["POST"])
@cross_origin()
def enhanced_search():
    """
    LLM-First Enhanced Book Search
    Uses LLM to understand the query, plan the search strategy, and enhance results
    """
    try:
        data = request.get_json()
        query = data.get("query")
        lang = data.get("lang", "en")  # Default to English

        if not query:
            return jsonify({"error": "Query is required"}), 400

        # Step 1: Use LLM to extract structured information from the query
        print(f"Extracting information from query: {query}")
        extracted_info = extract_book_info(query)
        print(f"Extracted info: {extracted_info}")

        # Step 2: Use LLM to create an intelligent search plan
        print("Creating intelligent search plan...")
        search_plan = intelligent_search_planning(query, extracted_info)
        print(f"Search plan: {search_plan}")

        # Step 3: Execute searches based on LLM's plan
        all_books = []
        
        # Determine search terms from LLM analysis
        search_terms = search_plan.get("search_terms", [query])
        if extracted_info.get("title"):
            search_terms.insert(0, extracted_info["title"])
        
        # Execute searches in priority order
        priority_sources = search_plan.get("priority_order", ["google_books", "gutendx", "aco"])
        
        for source in priority_sources:
            print(f"Searching {source}...")
            
            if source == "google_books" and "google_books" in search_plan.get("primary_sources", []):
                books = search_google_books(
                    search_terms, 
                    language=extracted_info.get("language", lang),
                    author=extracted_info.get("author")
                )
                all_books.extend(books)
            
            elif source == "gutendx" and "gutendx" in search_plan.get("primary_sources", []):
                books = search_gutendx(search_terms, language=extracted_info.get("language", lang))
                all_books.extend(books)
            
            elif source == "aco" and "aco" in search_plan.get("primary_sources", []):
                # Use enhanced Arabic search for better results
                if (extracted_info.get("language") == "ar" or 
                    any(c in "أب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه و ي" for c in query)):
                    aco_results = enhanced_arabic_search(query, sources=["aco", "rapidapi", "noor", "gutenberg"])
                    for aco_book in aco_results:
                        all_books.append({
                            "title": aco_book["title"],
                            "author": aco_book["author"],
                            "categories": aco_book.get("categories", []),
                            "description": aco_book.get("description", ""),
                            "thumbnail": None,
                            "info_link": None,
                            "pdf_links": aco_book["pdf_links"],
                            "source": aco_book["source"]
                        })
            
            elif source == "internet_archive" and "internet_archive" in search_plan.get("primary_sources", []):
                books = search_internet_archive(search_terms)
                all_books.extend(books)

        # Step 4: Merge duplicate books
        print("Merging duplicate books...")
        merged_books = merge_duplicate_books(all_books)

        # Step 5: Use LLM to enhance and rank results
        print("Enhancing search results with LLM...")
        enhanced_books, ranking_explanation = enhance_search_results(merged_books, query)

        # Step 6: Apply Arabic category localization if needed
        if extracted_info.get("language") == "ar" or lang == "ar":
            print("Applying Arabic category localization...")
            localized_books = []
            for book in enhanced_books:
                if book.get("categories"):
                    # Quick translate categories to Arabic
                    book["categories"] = quick_translate_categories(book["categories"])
                localized_books.append(book)
            enhanced_books = localized_books

        # Step 7: Return results with LLM insights
        return jsonify({
            "results": enhanced_books,
            "search_insights": {
                "extracted_info": extracted_info,
                "search_plan": search_plan,
                "ranking_explanation": ranking_explanation,
                "total_sources_searched": len(priority_sources),
                "total_results_found": len(enhanced_books)
            }
        })

    except requests.exceptions.RequestException as e:
        print(f"Error during enhanced search: {e}")
        return jsonify({"error": f"External API error: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "Internal server error"}), 500

@enhanced_book_bp.route("/convert-to-pdf", methods=["POST"])
@cross_origin()
def convert_to_pdf():
    try:
        data = request.get_json()
        file_url = data.get("file_url")
        output_filename = data.get("output_filename", "converted_book.pdf")

        if not file_url:
            return jsonify({"error": "File URL is required"}), 400

        # Download the file first
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        input_path = f"/tmp/{os.path.basename(file_url)}"
        with open(input_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        output_path = f"/tmp/{output_filename}"
        converter = EpubPdfConverter(input_path, output_path)
        converter.convert()

        # For now, we'll just return a success message. In a real deployment,
        # you'd need to serve this PDF or provide a temporary download link.
        # For Vercel, you might need to upload it to a storage service.
        return jsonify({"message": "Conversion successful", "download_path": output_path})

    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        return jsonify({"error": "PDF conversion failed"}), 500



@enhanced_book_bp.route("/localize-categories", methods=["POST"])
@cross_origin()
def localize_categories():
    """
    Endpoint to localize book categories to different languages
    """
    try:
        data = request.get_json()
        categories = data.get("categories", [])
        target_language = data.get("target_language", "ar")
        
        if not categories:
            return jsonify({"error": "Categories are required"}), 400
        
        if target_language == "ar":
            # Translate to Arabic
            localized_categories = quick_translate_categories(categories)
            return jsonify({
                "original_categories": categories,
                "localized_categories": localized_categories,
                "target_language": target_language
            })
        else:
            # For other languages, return original categories
            return jsonify({
                "original_categories": categories,
                "localized_categories": categories,
                "target_language": target_language,
                "message": f"Localization for {target_language} not yet supported"
            })
    
    except Exception as e:
        print(f"Error in localize_categories: {e}")
        return jsonify({"error": "Category localization failed"}), 500

@enhanced_book_bp.route("/category-mapping", methods=["GET"])
@cross_origin()
def get_category_mapping():
    """
    Get the predefined category mapping for Arabic
    """
    try:
        from src.routes.llm import get_arabic_category_mapping
        mapping = get_arabic_category_mapping()
        return jsonify({
            "mapping": mapping,
            "total_categories": len(mapping)
        })
    except Exception as e:
        print(f"Error getting category mapping: {e}")
        return jsonify({"error": "Failed to get category mapping"}), 500

