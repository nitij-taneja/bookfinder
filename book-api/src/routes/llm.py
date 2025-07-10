import os
import json
import requests
from flask import Blueprint, request, jsonify, session
from flask_cors import cross_origin
from groq import Groq

llm_bp = Blueprint("llm", __name__)

# Initialize Groq client with API key from environment variable
# It's safer to use environment variables for API keys in production
# For local testing, you can directly put your key here, but remove it before committing to public repo
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "your-secret-key-here")
client = Groq(api_key=GROQ_API_KEY)

# In-memory chat sessions storage (in production, use Redis or database)git rm --cached book-api/src/routes/llm.py

chat_sessions = {}

def search_books_for_pdf(query):
    """Search for books and return PDF links"""
    try:
        # Call our own PDF-priority search API
        response = requests.post(
            "http://localhost:5000/api/books/pdf-priority-search",
            json={"query": query, "lang": "en"},
            timeout=30
        )

        if response.ok:
            data = response.json()
            results = data.get("results", [])

            # Filter books that have PDF links
            pdf_books = [book for book in results if book.get("pdf_links")]

            return pdf_books[:5]  # Return top 5 PDF books

    except Exception as e:
        print(f"Error searching for PDFs: {e}")

    return []

def get_chat_session(session_id):
    """Get or create a chat session"""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "messages": [
                {
                    "role": "system",
                    "content": """You are a helpful AI book assistant. You can:
1. Recommend books based on user preferences
2. Provide information about books, authors, and genres
3. Search for and provide PDF download links for books
4. Answer questions about literature, reading, and book-related topics

When a user asks for a book or PDF, you should search for it and provide direct download links if available.
Be conversational and remember the context of our chat. Always be helpful and informative."""
                }
            ]
        }
    return chat_sessions[session_id]

@llm_bp.route("/chat", methods=["POST"])
@cross_origin()
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        # Get chat session with history
        chat_session = get_chat_session(session_id)

        # Add user message to history
        chat_session["messages"].append({
            "role": "user",
            "content": user_message
        })

        # Check if user is asking for a book or PDF
        book_request_keywords = ["pdf", "download", "book", "find", "search", "get me", "looking for"]
        is_book_request = any(keyword in user_message.lower() for keyword in book_request_keywords)

        enhanced_message = user_message
        pdf_results = []

        if is_book_request:
            # Try to extract book name from the message
            book_query = user_message
            # Remove common request words to get cleaner book title
            for word in ["find", "get", "download", "pdf", "book", "me", "the", "a", "an"]:
                book_query = book_query.replace(word, " ").strip()

            # Search for PDFs
            pdf_results = search_books_for_pdf(book_query)

            if pdf_results:
                pdf_info = "\n\nI found these PDF downloads for you:\n"
                for i, book in enumerate(pdf_results, 1):
                    pdf_info += f"\n{i}. **{book['title']}**"
                    if book.get('author'):
                        pdf_info += f" by {book['author']}"

                    for pdf_link in book.get('pdf_links', []):
                        pdf_info += f"\n   📄 Download PDF: {pdf_link['url']}"
                        pdf_info += f" (Source: {pdf_link['source']})"
                    pdf_info += "\n"

                enhanced_message += pdf_info

        # Create chat completion with full conversation history
        chat_completion = client.chat.completions.create(
            messages=chat_session["messages"],
            model="llama3-8b-8192",
            max_tokens=1000,
            temperature=0.7
        )

        llm_response = chat_completion.choices[0].message.content

        # If we found PDFs, append them to the response
        if pdf_results:
            llm_response += "\n\n📚 **PDF Downloads Found:**\n"
            for i, book in enumerate(pdf_results, 1):
                llm_response += f"\n{i}. **{book['title']}**"
                if book.get('author'):
                    llm_response += f" by {book['author']}"

                for pdf_link in book.get('pdf_links', []):
                    llm_response += f"\n   📄 [Download PDF]({pdf_link['url']}) (Source: {pdf_link['source']})"
                llm_response += "\n"

        # Add assistant response to history
        chat_session["messages"].append({
            "role": "assistant",
            "content": llm_response
        })

        # Keep only last 20 messages to prevent context from getting too long
        if len(chat_session["messages"]) > 20:
            # Keep system message and last 19 messages
            chat_session["messages"] = [chat_session["messages"][0]] + chat_session["messages"][-19:]

        return jsonify({
            "response": llm_response,
            "session_id": session_id,
            "pdf_results": pdf_results
        })

    except Exception as e:
        print(f"Error in LLM chat: {e}")
        return jsonify({"error": "Internal server error"}), 500

@llm_bp.route("/related-books", methods=["POST"])
@cross_origin()
def related_books():
    try:
        data = request.get_json()
        book_title = data.get("title")
        book_author = data.get("author")
        
        if not book_title:
            return jsonify({"error": "Book title is required"}), 400

        prompt = f"Suggest 3-5 books similar to \'{book_title}\' by {book_author if book_author else 'an unknown author'}. Provide only the book titles and authors, one per line, in the format: Title - Author."

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
        )

        llm_response = chat_completion.choices[0].message.content
        
        # Parse the response into a list of dictionaries
        related_books_list = []
        for line in llm_response.split("\n"):
            if " - " in line:
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    related_books_list.append({"title": parts[0].strip(), "author": parts[1].strip()})
        
        return jsonify({"related_books": related_books_list})

    except Exception as e:
        print(f"Error in related books suggestion: {e}")
        return jsonify({"error": "Internal server error"}), 500




def extract_book_info(query):
    """
    Extract structured book information from a natural language query using LLM
    """
    try:
        prompt = f"""
        Extract book information from this query: "{query}"
        
        Please respond with a JSON object containing:
        - title: The book title (if mentioned)
        - author: The author name (if mentioned)
        - categories: List of relevant book categories/genres
        - language: Detected language of the query ("en" for English, "ar" for Arabic, etc.)
        - search_strategy: Recommended search approach ("general", "academic", "fiction", "arabic_specific", etc.)
        - keywords: List of important keywords for searching
        
        If information is not available, use null for strings/arrays or empty array for lists.
        Respond only with valid JSON.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
        )

        llm_response = chat_completion.choices[0].message.content
        
        # Try to parse JSON response
        try:
            import json
            return json.loads(llm_response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "title": None,
                "author": None,
                "categories": [],
                "language": "en",
                "search_strategy": "general",
                "keywords": [query]
            }

    except Exception as e:
        print(f"Error in extract_book_info: {e}")
        return {
            "title": None,
            "author": None,
            "categories": [],
            "language": "en",
            "search_strategy": "general",
            "keywords": [query]
        }

def intelligent_search_planning(query, extracted_info):
    """
    Use LLM to create an intelligent search plan based on the query and extracted information
    """
    try:
        prompt = f"""
        Based on this book search query: "{query}"
        And extracted information: {extracted_info}
        
        Create a search plan with the following JSON structure:
        {{
            "primary_sources": ["google_books", "gutendex", "aco", "internet_archive"],
            "search_terms": ["term1", "term2"],
            "filters": {{
                "language": "en/ar",
                "category": "category_if_specific",
                "availability": "free/paid/any"
            }},
            "priority_order": ["source1", "source2"],
            "expected_results": "description of what type of results to expect"
        }}
        
        Consider:
        - If query is in Arabic or mentions Arabic books, prioritize ACO
        - If looking for classic/public domain books, prioritize Gutendex
        - For general search with covers/descriptions, prioritize Google Books
        - For academic/research books, consider Internet Archive
        
        Respond only with valid JSON.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
        )

        llm_response = chat_completion.choices[0].message.content
        
        try:
            import json
            return json.loads(llm_response)
        except json.JSONDecodeError:
            # Fallback plan
            return {
                "primary_sources": ["google_books", "gutendx", "aco"],
                "search_terms": [query],
                "filters": {
                    "language": extracted_info.get("language", "en"),
                    "category": None,
                    "availability": "any"
                },
                "priority_order": ["google_books", "gutendx", "aco"],
                "expected_results": "General book search results"
            }

    except Exception as e:
        print(f"Error in intelligent_search_planning: {e}")
        return {
            "primary_sources": ["google_books", "gutendx", "aco"],
            "search_terms": [query],
            "filters": {
                "language": extracted_info.get("language", "en"),
                "category": None,
                "availability": "any"
            },
            "priority_order": ["google_books", "gutendx", "aco"],
            "expected_results": "General book search results"
        }

def enhance_search_results(results, original_query):
    """
    Use LLM to enhance and rank search results based on relevance to the original query
    """
    try:
        # Prepare a summary of results for LLM analysis
        results_summary = []
        for i, book in enumerate(results[:10]):  # Limit to first 10 for LLM processing
            results_summary.append({
                "index": i,
                "title": book.get("title", ""),
                "author": book.get("author", ""),
                "categories": book.get("categories", [])
            })

        prompt = f"""
        Original search query: "{original_query}"
        Search results: {results_summary}
        
        Please analyze these results and provide:
        1. Relevance scores (0-100) for each result
        2. Reordered indices based on relevance
        3. Brief explanation of why certain results are more relevant
        
        Respond with JSON:
        {{
            "relevance_scores": [score1, score2, ...],
            "reordered_indices": [index1, index2, ...],
            "explanation": "Brief explanation of ranking logic"
        }}
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
        )

        llm_response = chat_completion.choices[0].message.content
        
        try:
            import json
            enhancement_data = json.loads(llm_response)
            
            # Reorder results based on LLM recommendations
            reordered_indices = enhancement_data.get("reordered_indices", list(range(len(results))))
            enhanced_results = []
            
            for idx in reordered_indices:
                if idx < len(results):
                    enhanced_results.append(results[idx])
            
            # Add any remaining results that weren't reordered
            for i, result in enumerate(results):
                if i not in reordered_indices:
                    enhanced_results.append(result)
            
            return enhanced_results, enhancement_data.get("explanation", "")
            
        except json.JSONDecodeError:
            return results, "Unable to enhance results ranking"

    except Exception as e:
        print(f"Error in enhance_search_results: {e}")
        return results, "Error in result enhancement"



def translate_categories_to_arabic(categories):
    """
    Translate English book categories to Arabic using LLM
    """
    try:
        if not categories or len(categories) == 0:
            return []
        
        categories_str = ", ".join(categories)
        
        prompt = f"""
        Translate these book categories from English to Arabic. Provide accurate, commonly used Arabic terms for book categories.
        
        Categories to translate: {categories_str}
        
        Please respond with a JSON array of Arabic translations in the same order as the input categories.
        For example: ["الأدب", "التاريخ", "العلوم"]
        
        If a category doesn't have a direct Arabic equivalent, provide the closest meaningful Arabic term.
        Respond only with the JSON array.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
        )

        llm_response = chat_completion.choices[0].message.content
        
        try:
            import json
            arabic_categories = json.loads(llm_response)
            return arabic_categories if isinstance(arabic_categories, list) else []
        except json.JSONDecodeError:
            # Fallback: try to extract categories from response
            lines = llm_response.split('\n')
            arabic_categories = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('[') and not line.startswith(']'):
                    # Remove quotes and commas
                    clean_line = line.replace('"', '').replace(',', '').strip()
                    if clean_line:
                        arabic_categories.append(clean_line)
            return arabic_categories[:len(categories)]  # Limit to original count

    except Exception as e:
        print(f"Error in translate_categories_to_arabic: {e}")
        return categories  # Return original categories as fallback

def localize_book_categories(book_data, target_language="ar"):
    """
    Localize book categories based on target language
    """
    try:
        if target_language != "ar":
            return book_data  # No localization needed for non-Arabic
        
        if not book_data.get("categories"):
            return book_data
        
        # Check if categories are already in Arabic
        categories = book_data["categories"]
        has_arabic = any(any(c in "أب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه و ي" for c in cat) for cat in categories)
        
        if has_arabic:
            # Categories already contain Arabic, no translation needed
            return book_data
        
        # Translate categories to Arabic
        arabic_categories = translate_categories_to_arabic(categories)
        
        # Create localized book data
        localized_data = book_data.copy()
        localized_data["categories"] = arabic_categories
        localized_data["original_categories"] = categories  # Keep original for reference
        
        return localized_data

    except Exception as e:
        print(f"Error in localize_book_categories: {e}")
        return book_data

def get_arabic_category_mapping():
    """
    Get a predefined mapping of common English to Arabic book categories
    """
    return {
        "Fiction": "الأدب الخيالي",
        "Non-fiction": "الأدب غير الخيالي", 
        "History": "التاريخ",
        "Science": "العلوم",
        "Technology": "التكنولوجيا",
        "Philosophy": "الفلسفة",
        "Religion": "الدين",
        "Biography": "السيرة الذاتية",
        "Poetry": "الشعر",
        "Drama": "المسرح",
        "Literature": "الأدب",
        "Education": "التعليم",
        "Psychology": "علم النفس",
        "Medicine": "الطب",
        "Law": "القانون",
        "Economics": "الاقتصاد",
        "Politics": "السياسة",
        "Art": "الفن",
        "Music": "الموسيقى",
        "Sports": "الرياضة",
        "Travel": "السفر",
        "Cooking": "الطبخ",
        "Health": "الصحة",
        "Business": "الأعمال",
        "Self-help": "تطوير الذات",
        "Romance": "الرومانسية",
        "Mystery": "الغموض",
        "Thriller": "الإثارة",
        "Horror": "الرعب",
        "Fantasy": "الخيال",
        "Science Fiction": "الخيال العلمي",
        "Children": "الأطفال",
        "Young Adult": "الشباب",
        "Comics": "الكوميكس",
        "Reference": "المراجع",
        "Textbook": "الكتب المدرسية",
        "Academic": "الأكاديمي",
        "Research": "البحث",
        "Mathematics": "الرياضيات",
        "Physics": "الفيزياء",
        "Chemistry": "الكيمياء",
        "Biology": "الأحياء",
        "Geography": "الجغرافيا",
        "Sociology": "علم الاجتماع",
        "Anthropology": "علم الإنسان",
        "Linguistics": "علم اللغة",
        "Journalism": "الصحافة",
        "Media": "الإعلام"
    }

def quick_translate_categories(categories):
    """
    Quick translation using predefined mapping, fallback to LLM for unknown categories
    """
    try:
        mapping = get_arabic_category_mapping()
        translated = []
        unknown_categories = []
        
        for category in categories:
            if category in mapping:
                translated.append(mapping[category])
            else:
                unknown_categories.append(category)
                translated.append(category)  # Keep original for now
        
        # Use LLM for unknown categories
        if unknown_categories:
            llm_translations = translate_categories_to_arabic(unknown_categories)
            
            # Replace unknown categories with LLM translations
            unknown_index = 0
            for i, category in enumerate(categories):
                if category in unknown_categories:
                    if unknown_index < len(llm_translations):
                        translated[i] = llm_translations[unknown_index]
                    unknown_index += 1
        
        return translated
        
    except Exception as e:
        print(f"Error in quick_translate_categories: {e}")
        return categories

