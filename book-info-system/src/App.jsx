import { useState, useEffect } from 'react'
import { Search, Book, Globe, Download, User, Tag, MessageSquare, CornerDownLeft, Maximize2, Minimize2, X, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { ScrollArea } from '@/components/ui/scroll-area.jsx'
import './App.css'

function App() {
  const [searchQuery, setSearchQuery] = useState('')
  const [language, setLanguage] = useState('en') // 'en' or 'ar'
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [llmLoading, setLlmLoading] = useState(false)
  const [chatMaximized, setChatMaximized] = useState(false)
  const [chatVisible, setChatVisible] = useState(true)
  const [chatSessionId, setChatSessionId] = useState(() => {
    // Generate a unique session ID for this chat session
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
  })

  const t = {
    en: {
      title: 'Book Information Retrieval System',
      searchPlaceholder: 'Enter book name or ask a question...', // Updated placeholder
      searchButton: 'Search Books',
      categories: 'Categories',
      downloadPdf: 'Download PDF',
      publicDomain: 'Public Domain - Free to Download',
      noResults: 'No books found. Try a different search term.',
      error: 'An error occurred while searching. Please try again.',
      loading: 'Searching for books...', // For book search
      pdfLinks: 'PDF Downloads',
      convert: 'Convert',
      download: 'Download',
      chatTitle: 'AI Assistant',
      chatPlaceholder: 'Ask me anything about books...', // Chat placeholder
      sendMessage: 'Send',
      llmLoading: 'AI is thinking...', // For LLM chat
      relatedBooks: 'Related Books',
      askAboutBook: 'Ask AI about this book',
      askAboutRelated: 'Get related books from AI'
    },
    ar: {
      title: 'نظام استرجاع معلومات الكتب',
      searchPlaceholder: 'أدخل اسم الكتاب أو اطرح سؤالاً...', // Updated placeholder
      searchButton: 'البحث عن الكتب',
      categories: 'التصنيفات',
      downloadPdf: 'تحميل PDF',
      publicDomain: 'ملكية عامة - مجاني للتحميل',
      noResults: 'لم يتم العثور على كتب. جرب مصطلح بحث مختلف.',
      error: 'حدث خطأ أثناء البحث. يرجى المحاولة مرة أخرى.',
      loading: 'البحث عن الكتب...', // For book search
      pdfLinks: 'تحميلات PDF',
      convert: 'تحويل',
      download: 'تحميل',
      chatTitle: 'مساعد الذكاء الاصطناعي',
      chatPlaceholder: 'اسألني أي شيء عن الكتب...', // Chat placeholder
      sendMessage: 'إرسال',
      llmLoading: 'الذكاء الاصطناعي يفكر...', // For LLM chat
      relatedBooks: 'كتب ذات صلة',
      askAboutBook: 'اسأل الذكاء الاصطناعي عن هذا الكتاب',
      askAboutRelated: 'احصل على كتب ذات صلة من الذكاء الاصطناعي'
    }
  }[language];

  useEffect(() => {
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
  }, [language]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError('');
    setBooks([]);
    
    try {
      const response = await fetch('/api/books/pdf-priority-search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: searchQuery,
          lang: language // Pass language to backend
        }),
      });
      
      if (!response.ok) {
        throw new Error('Search failed');
      }
      
      const data = await response.json();
      setBooks(data.results || []);
    } catch (err) {
      setError('Failed to search books. Please try again.');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConvertToPdf = async (url, format) => {
    try {
      const response = await fetch('/api/books/convert-to-pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_url: url,
          output_filename: `converted_book.${format}.pdf` // Ensure unique name
        }),
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `converted_book.${format}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
      } else {
        alert('Conversion failed. Please try again.');
      }
    } catch (err) {
      console.error('Conversion error:', err);
      alert('Conversion failed. Please try again.');
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;

    const userMessage = chatInput;
    setChatMessages(prev => [...prev, { sender: 'user', text: userMessage }]);
    setChatInput('');
    setLlmLoading(true);

    try {
      const response = await fetch('/api/llm/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: chatSessionId
        }),
      });

      if (!response.ok) {
        throw new Error('LLM chat failed');
      }

      const data = await response.json();

      // Add AI response to chat
      setChatMessages(prev => [...prev, {
        sender: 'ai',
        text: data.response,
        pdfResults: data.pdf_results || []
      }]);

    } catch (err) {
      console.error('LLM chat error:', err);
      setChatMessages(prev => [...prev, { sender: 'ai', text: t.error }]);
    } finally {
      setLlmLoading(false);
    }
  };

  const clearChatHistory = () => {
    setChatMessages([]);
    // Generate new session ID for fresh conversation
    setChatSessionId('session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9));
  };

  const handleGetRelatedBooks = async (title, author) => {
    setLlmLoading(true);
    setChatMessages(prev => [...prev, { sender: 'user', text: `${t.askAboutRelated}: ${title} by ${author}` }]);

    try {
      const response = await fetch('/api/llm/related-books', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title, author }),
      });

      if (!response.ok) {
        throw new Error('Related books failed');
      }

      const data = await response.json();
      if (data.related_books && data.related_books.length > 0) {
        const relatedText = data.related_books.map(b => `${b.title} - ${b.author}`).join('\n');
        setChatMessages(prev => [...prev, { sender: 'ai', text: `${t.relatedBooks}:\n${relatedText}` }]);
      } else {
        setChatMessages(prev => [...prev, { sender: 'ai', text: 'No related books found.' }]);
      }
    } catch (err) {
      console.error('Related books error:', err);
      setChatMessages(prev => [...prev, { sender: 'ai', text: t.error }]);
    } finally {
      setLlmLoading(false);
    }
  };

  const handleAskAboutBook = async (title, author, description) => {
    const prompt = `Tell me about the book: ${title} by ${author}. Here is a brief description: ${description}.`;
    setChatMessages(prev => [...prev, { sender: 'user', text: `${t.askAboutBook}: ${title}` }]);
    setLlmLoading(true);

    try {
      const response = await fetch('/api/llm/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: prompt }),
      });

      if (!response.ok) {
        throw new Error('LLM chat failed');
      }

      const data = await response.json();
      setChatMessages(prev => [...prev, { sender: 'ai', text: data.response }]);
    } catch (err) {
      console.error('LLM chat error:', err);
      setChatMessages(prev => [...prev, { sender: 'ai', text: t.error }]);
    } finally {
      setLlmLoading(false);
    }
  };

  const toggleLanguage = () => {
    setLanguage(language === 'en' ? 'ar' : 'en')
  }

  return (
    <div className={`min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 ${language === 'ar' ? 'rtl' : 'ltr'}`}>
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <Book className="h-8 w-8 text-blue-600" />
              <span className="text-xl font-bold text-blue-600">BookFinder AI</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleLanguage}
              className="flex items-center gap-2"
            >
              <Globe className="h-4 w-4" />
              {language === 'en' ? 'العربية' : 'English'}
            </Button>
          </div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">{t.title}</h1>
          <p className="text-lg text-gray-600">{t.subtitle}</p>
        </div>

        {/* Search Section */}
        <Card className="max-w-2xl mx-auto mb-8">
          <CardContent className="p-6">
            <div className="flex gap-4">
              <div className="flex-1">
                <Input
                  type="text"
                  placeholder={t.searchPlaceholder}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  className="text-lg"
                  dir={language === 'ar' ? 'rtl' : 'ltr'}
                />
              </div>
              <Button
                onClick={handleSearch}
                disabled={loading || !searchQuery.trim()}
                className="px-6"
              >
                <Search className="h-4 w-4 mr-2" />
                {t.searchButton}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">{t.loading}</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="max-w-2xl mx-auto mb-8">
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-4">
                <p className="text-red-600 text-center">{error}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Results */}
        {books.length > 0 && (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {books.map((book, index) => (
              <Card key={book.id || index} className="overflow-hidden hover:shadow-lg transition-shadow">
                <CardHeader className="pb-4">
                  <div className="flex gap-4">
                    <img
                      src={book.thumbnail || '/api/placeholder/120/180'}
                      alt={book.title}
                      className="w-20 h-30 object-cover rounded"
                      onError={(e) => {
                        e.target.src = '/api/placeholder/120/180'
                      }}
                    />
                    <div className="flex-1">
                      <CardTitle className="text-lg mb-2 line-clamp-2">{book.title}</CardTitle>
                      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                        <User className="h-4 w-4" />
                        <span>{book.author}</span>
                      </div>
                      {book.description && (
                        <p className="text-xs text-gray-500 line-clamp-3">{book.description}</p>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Tag className="h-4 w-4 text-gray-500" />
                        <span className="text-sm font-medium">{t.categories}</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {book.categories.map((category, catIndex) => (
                          <Badge key={catIndex} variant="secondary" className="text-xs">
                            {category}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    
                    {book.pdf_links && book.pdf_links.length > 0 && (
                      <div className="pt-2">
                        <div className="flex items-center gap-2 mb-2">
                          <Download className="h-4 w-4 text-green-600" />
                          <span className="text-sm font-medium text-green-700">{t.pdfLinks}</span>
                          <Badge variant="secondary" className="text-xs bg-green-100 text-green-800">
                            {book.pdf_links.length} PDF{book.pdf_links.length > 1 ? 's' : ''}
                          </Badge>
                        </div>
                        <div className="space-y-2">
                          {book.pdf_links.map((link, linkIndex) => (
                            <div key={linkIndex} className="flex items-center justify-between bg-green-50 border border-green-200 p-3 rounded-lg">
                              <div className="flex items-center gap-2">
                                <Download className="h-4 w-4 text-green-600" />
                                <div>
                                  <div className="text-sm font-medium text-green-800">
                                    {link.source}
                                  </div>
                                  <div className="text-xs text-green-600">
                                    {t.publicDomain}
                                  </div>
                                </div>
                              </div>
                              {link.type === 'convertible' ? (
                                <Button
                                  onClick={() => handleConvertToPdf(link.url, link.format)}
                                  size="sm"
                                  className="bg-green-600 hover:bg-green-700 text-white"
                                >
                                  <Download className="h-3 w-3 mr-1" />
                                  {t.convert}
                                </Button>
                              ) : (
                                <Button
                                  asChild
                                  size="sm"
                                  className="bg-green-600 hover:bg-green-700 text-white"
                                >
                                  <a href={link.url} target="_blank" rel="noopener noreferrer">
                                    <Download className="h-3 w-3 mr-1" />
                                    {t.downloadPdf}
                                  </a>
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="flex flex-col gap-2 pt-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => handleAskAboutBook(book.title, book.author, book.description)}
                      >
                        {t.askAboutBook}
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => handleGetRelatedBooks(book.title, book.author)}
                      >
                        {t.askAboutRelated}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* No Results */}
        {!loading && !error && books.length === 0 && searchQuery && (
          <div className="text-center py-8">
            <Book className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">{t.noResults}</p>
          </div>
        )}

        {/* AI Assistant Chatbot */}
        {chatVisible && (
          <Card className={`fixed ${chatMaximized ? 'inset-4' : 'bottom-4 right-4 w-96 h-[500px]'} flex flex-col shadow-xl z-50 transition-all duration-300`}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 border-b bg-blue-50">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-blue-600" />
                <CardTitle className="text-lg font-semibold text-blue-800">{t.chatTitle}</CardTitle>
                <div className="text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded">
                  Continuous Chat
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={clearChatHistory}
                  className="h-8 w-8 hover:bg-yellow-100"
                  title="Clear chat history"
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setChatMaximized(!chatMaximized)}
                  className="h-8 w-8 hover:bg-blue-100"
                >
                  {chatMaximized ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setChatVisible(false)}
                  className="h-8 w-8 hover:bg-red-100"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 p-4 overflow-hidden bg-white">
              <ScrollArea className="h-full pr-4">
                <div className="space-y-4">
                  {chatMessages.length === 0 && (
                    <div className="text-center text-gray-500 py-8">
                      <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p className="text-sm font-medium">AI Book Assistant - Continuous Chat</p>
                      <p className="text-xs mt-2">I can help you find books and provide PDF downloads!</p>
                      <div className="mt-3 text-xs space-y-1">
                        <p>• "Find me Rich Dad Poor Dad PDF"</p>
                        <p>• "Recommend finance books"</p>
                        <p>• "Tell me about [book name]"</p>
                        <p>• "Get me PDF of [book name]"</p>
                      </div>
                      <p className="text-xs mt-3 text-blue-600">💡 I remember our conversation!</p>
                    </div>
                  )}
                  {chatMessages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] p-3 rounded-lg shadow-sm ${
                          msg.sender === 'user'
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-800 border'
                        }`}
                      >
                        <div className="text-sm leading-relaxed whitespace-pre-wrap">
                          {msg.text}
                        </div>

                        {/* Display PDF results if available */}
                        {msg.pdfResults && msg.pdfResults.length > 0 && (
                          <div className="mt-3 space-y-2">
                            <div className="text-xs font-medium text-green-700 flex items-center gap-1">
                              <Download className="h-3 w-3" />
                              PDF Downloads Found:
                            </div>
                            {msg.pdfResults.map((book, bookIndex) => (
                              <div key={bookIndex} className="bg-green-50 border border-green-200 p-2 rounded text-xs">
                                <div className="font-medium text-green-800">{book.title}</div>
                                {book.author && (
                                  <div className="text-green-600 text-xs">by {book.author}</div>
                                )}
                                <div className="mt-1 space-y-1">
                                  {book.pdf_links?.map((link, linkIndex) => (
                                    <a
                                      key={linkIndex}
                                      href={link.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-green-700 hover:text-green-900 underline text-xs"
                                    >
                                      <Download className="h-3 w-3" />
                                      Download PDF ({link.source})
                                    </a>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {llmLoading && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] p-3 rounded-lg bg-gray-100 text-gray-800 border animate-pulse">
                        <div className="flex items-center gap-2">
                          <div className="flex space-x-1">
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                          </div>
                          <span className="text-sm">{t.llmLoading}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
            <div className="p-4 border-t bg-gray-50 flex items-center gap-2">
              <Input
                placeholder={t.chatPlaceholder}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleChat()}
                className="flex-1 bg-white"
                dir={language === 'ar' ? 'rtl' : 'ltr'}
              />
              <Button
                size="icon"
                onClick={handleChat}
                disabled={llmLoading || !chatInput.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <CornerDownLeft className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        )}

        {/* Chat Toggle Button (when chat is hidden) */}
        {!chatVisible && (
          <Button
            onClick={() => setChatVisible(true)}
            className="fixed bottom-4 right-4 h-14 w-14 rounded-full bg-blue-600 hover:bg-blue-700 shadow-lg z-50"
            size="icon"
          >
            <MessageSquare className="h-6 w-6" />
          </Button>
        )}

      </div>
    </div>
  )
}

export default App



