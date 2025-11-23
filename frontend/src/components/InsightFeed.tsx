import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface InsightSummary {
  id: string;
  text: string;
  category: string;
  similarity_score: number;
}

interface SourceCard {
  id: string;
  source_url: string;
  source_domain: string;
  title: string;
  insights: InsightSummary[];
  insight_count: number;
  created_at: string;
  relevance_score: number;
  topics: string[];
}

interface Interest {
  id: number;
  topic: string;
  created_at: string;
}

export function InsightFeed() {
  const [sources, setSources] = useState<SourceCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [interests, setInterests] = useState<Interest[]>([]);
  const [newInterest, setNewInterest] = useState('');
  const [likedInsights, setLikedInsights] = useState<Set<string>>(new Set());
  const [bookmarkedInsights, setBookmarkedInsights] = useState<Set<string>>(new Set());
  const [showSuggestions, setShowSuggestions] = useState(false);

  // API URL - use relative URLs in production (goes through nginx proxy)
  const API_URL = import.meta.env.VITE_API_URL || '';

  useEffect(() => {
    loadInterests();
    loadFeed();
  }, []);

  const loadInterests = () => {
    // Load interests from localStorage (per-user/browser)
    try {
      const stored = localStorage.getItem('userInterests');
      const data = stored ? JSON.parse(stored) : [];
      setInterests(data);
      setShowSuggestions(data.length === 0);
    } catch (error) {
      console.error('Failed to load interests:', error);
      setInterests([]);
    }
  };

  const loadFeed = async () => {
    try {
      // Get interests from localStorage and send to backend
      const stored = localStorage.getItem('userInterests');
      const userInterests = stored ? JSON.parse(stored) : [];
      const topics = userInterests.map((i: any) => i.topic).join(',');
      
      const response = await fetch(`${API_URL}/api/feed?limit=50&interests=${encodeURIComponent(topics)}`);
      const data = await response.json();
      setSources(data);
    } catch (error) {
      console.error('Failed to load feed:', error);
    } finally {
      setLoading(false);
    }
  };

  const addInterest = async () => {
    if (!newInterest.trim()) return;

    try {
      // Add to localStorage instead of backend
      const newInterestObj = {
        id: Date.now(), // Use timestamp as ID
        topic: newInterest,
        created_at: new Date().toISOString()
      };
      
      const updatedInterests = [...interests, newInterestObj];
      localStorage.setItem('userInterests', JSON.stringify(updatedInterests));
      
      setNewInterest('');
      loadInterests();
      await loadFeed(); // Refresh feed with new interest
    } catch (error) {
      console.error('Failed to add interest:', error);
    }
  };

  const deleteInterest = async (id: number) => {
    try {
      // Remove from localStorage
      const updatedInterests = interests.filter(i => i.id !== id);
      localStorage.setItem('userInterests', JSON.stringify(updatedInterests));
      
      loadInterests();
      await loadFeed(); // Refresh feed
    } catch (error) {
      console.error('Failed to delete interest:', error);
    }
  };

  const suggestedTopics = [
    'AI agents & automation',
    'Startup ideas & trends',
    'Value investing',
    'Future of work',
    'Labor market trends',
    'Gen Z consumer behavior',
  ];

  const handleEngagement = async (insightId: string, action: 'like' | 'bookmark' | 'x') => {
    // Record engagement
    await fetch(`${API_URL}/api/feed/engage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        insight_id: insightId,
        action
      })
    });

    // Handle different actions
    if (action === 'x') {
      // Remove card from view immediately
      setSources(sources.filter(source => source.id !== insightId));
    } else if (action === 'like') {
      // Toggle like
      const newLiked = new Set(likedInsights);
      if (newLiked.has(insightId)) {
        newLiked.delete(insightId);
      } else {
        newLiked.add(insightId);
      }
      setLikedInsights(newLiked);
    } else if (action === 'bookmark') {
      // Toggle bookmark
      const newBookmarked = new Set(bookmarkedInsights);
      if (newBookmarked.has(insightId)) {
        newBookmarked.delete(insightId);
      } else {
        newBookmarked.add(insightId);
      }
      setBookmarkedInsights(newBookmarked);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header with Interests Management */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Feed Focus</h1>
          
          {/* Add Interest */}
          <div className="mb-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={newInterest}
                onChange={(e) => setNewInterest(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addInterest()}
                placeholder="Add an interest (e.g., AI agents, labor market)..."
                className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-sm"
              />
              <button
                onClick={addInterest}
                disabled={!newInterest.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                Add
              </button>
              <button
                onClick={() => setShowSuggestions(!showSuggestions)}
                className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition text-sm"
              >
                {showSuggestions ? '✕' : '💡'}
              </button>
            </div>
          </div>

          {/* Suggestions */}
          {showSuggestions && (
            <div className="mb-3">
              <div className="flex flex-wrap gap-2">
                {suggestedTopics.map((topic) => (
                  <button
                    key={topic}
                    onClick={() => {
                      setNewInterest(topic);
                      setShowSuggestions(false);
                    }}
                    className="px-3 py-1.5 bg-gray-50 text-gray-700 rounded-md text-sm hover:bg-gray-100 border border-gray-200"
                  >
                    {topic}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Current Interests */}
          {interests.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {interests.map((interest) => (
                <div
                  key={interest.id}
                  className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm flex items-center gap-2 border border-blue-200"
                >
                  <span>{interest.topic}</span>
                  <button
                    onClick={() => deleteInterest(interest.id)}
                    className="hover:bg-blue-100 rounded-full w-4 h-4 flex items-center justify-center text-xs"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {!loading && sources.length > 0 && (
            <p className="text-xs text-gray-500 mt-2">{sources.reduce((sum, s) => sum + s.insight_count, 0)} new insights</p>
          )}
        </div>
      </div>

      {/* Empty State */}
      {!loading && sources.length === 0 && (
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            {interests.length === 0 ? 'Add interests to get started' : 'No insights yet'}
          </h2>
          <p className="text-gray-600 text-sm">
            {interests.length === 0 
              ? 'Add topics above to discover personalized insights'
              : 'We\'re finding insights for your interests...'}
          </p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <div className="inline-block w-8 h-8 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-600">Loading insights...</p>
        </div>
      )}

      {/* Feed - Venmo Style */}
      {!loading && sources.length > 0 && (
        <div className="max-w-2xl mx-auto px-4 py-3 space-y-0 divide-y divide-gray-100">
          {sources.map((source, index) => (
          <motion.div
            key={source.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.03 }}
            className="bg-white py-5"
          >
            <div className="flex gap-3">
              {/* Source Icon/Avatar */}
              <div className="flex-shrink-0">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
                  {source.source_domain.charAt(0).toUpperCase()}
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                {/* Header */}
                <div className="flex items-center gap-2 mb-2">
                  <a 
                    href={source.source_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="font-semibold text-gray-900 hover:underline text-sm"
                  >
                    {source.source_domain}
                  </a>
                  <span className="text-gray-400 text-xs">•</span>
                  <span className="text-gray-500 text-xs">
                    {new Date(source.created_at).toLocaleDateString('en-US', { 
                      month: 'short', 
                      day: 'numeric' 
                    })}
                  </span>
                  <button
                    onClick={() => handleEngagement(source.id, 'x')}
                    className="ml-auto p-1 text-gray-400 hover:text-gray-600 transition"
                    title="Not interested"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Insights */}
                <div className="space-y-4 mb-4">
                  {source.insights && source.insights.length > 0 ? (
                    source.insights.map((insight) => {
                      const lines = insight.text.split('\n');
                      const categoryLine = lines[0];
                      const insightText = lines.slice(1).join('\n');
                      
                      return (
                        <div key={insight.id} className="space-y-1">
                          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                            {categoryLine}
                          </div>
                          <p className="text-gray-900 text-sm leading-relaxed">
                            {insightText || insight.text}
                          </p>
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-sm text-gray-500">No insights available</p>
                  )}
                </div>

                {/* Action Buttons - X.com Style */}
                <div className="flex items-center gap-6 pt-2">
                  {/* Like Button */}
                  <button
                    onClick={() => handleEngagement(source.id, 'like')}
                    className="group flex items-center gap-2 text-gray-500 hover:text-red-500 transition"
                  >
                    {likedInsights.has(source.id) ? (
                      <svg className="w-5 h-5 fill-red-500" viewBox="0 0 24 24">
                        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 stroke-current fill-none" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                      </svg>
                    )}
                  </button>

                  {/* Bookmark Button */}
                  <button
                    onClick={() => handleEngagement(source.id, 'bookmark')}
                    className="group flex items-center gap-2 text-gray-500 hover:text-blue-500 transition"
                  >
                    {bookmarkedInsights.has(source.id) ? (
                      <svg className="w-5 h-5 fill-blue-500" viewBox="0 0 24 24">
                        <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 stroke-current fill-none" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
          ))}
        </div>
      )}

      {/* Load More */}
      {!loading && sources.length > 0 && (
        <div className="max-w-4xl mx-auto px-4 py-8 text-center">
          <button
            onClick={loadFeed}
            className="px-6 py-3 bg-white border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 transition"
          >
            Load More
          </button>
        </div>
      )}
    </div>
  );
}

// Removed getCategoryColor - now using inline emoji categories from backend
