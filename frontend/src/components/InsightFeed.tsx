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
  const [interests, setInterests] = useState<Interest[]>([]);
  const [newInterest, setNewInterest] = useState('');
  const [loading, setLoading] = useState(true);
  const [likedInsights, setLikedInsights] = useState<Set<string>>(new Set());
  const [bookmarkedInsights, setBookmarkedInsights] = useState<Set<string>>(new Set());
  const [showSuggestions, setShowSuggestions] = useState(false);

  // API URL - use relative URLs in production (goes through nginx proxy)
  const API_URL = import.meta.env.VITE_API_URL || '';

  useEffect(() => {
    loadInterests();
    loadFeed();
    loadEngagements();
  }, []);

  const loadEngagements = () => {
    // Load liked and bookmarked insights from localStorage
    try {
      const liked = localStorage.getItem('likedInsights');
      const bookmarked = localStorage.getItem('bookmarkedInsights');
      if (liked) setLikedInsights(new Set(JSON.parse(liked)));
      if (bookmarked) setBookmarkedInsights(new Set(JSON.parse(bookmarked)));
    } catch (error) {
      console.error('Failed to load engagements:', error);
    }
  };

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
    if (action === 'x') {
      // Dismiss card - remove from view
      setSources(sources.filter(source => source.id !== insightId));
      
      // Record dismissal
      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ insight_id: insightId, action })
      });
    } else if (action === 'like') {
      // Toggle like
      const newLiked = new Set(likedInsights);
      const isLiked = newLiked.has(insightId);
      
      if (isLiked) {
        newLiked.delete(insightId);
      } else {
        newLiked.add(insightId);
      }
      
      setLikedInsights(newLiked);
      localStorage.setItem('likedInsights', JSON.stringify([...newLiked]));
      
      // Record engagement (or un-engagement)
      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ insight_id: insightId, action: isLiked ? 'unlike' : 'like' })
      });
    } else if (action === 'bookmark') {
      // Toggle bookmark
      const newBookmarked = new Set(bookmarkedInsights);
      const isBookmarked = newBookmarked.has(insightId);
      
      if (isBookmarked) {
        newBookmarked.delete(insightId);
      } else {
        newBookmarked.add(insightId);
      }
      
      setBookmarkedInsights(newBookmarked);
      localStorage.setItem('bookmarkedInsights', JSON.stringify([...newBookmarked]));
      
      // Record engagement (or un-engagement)
      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ insight_id: insightId, action: isBookmarked ? 'unbookmark' : 'bookmark' })
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
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

          {!loading && (
            <p className="text-xs text-gray-500">{sources.length} sources • {sources.reduce((sum, s) => sum + s.insight_count, 0)} insights</p>
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

      {/* Feed */}
      {!loading && sources.length > 0 && (
        <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
          {sources.map((source, index) => (
          <motion.div
            key={source.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className="bg-white border border-gray-200 rounded-xl hover:shadow-lg transition-shadow overflow-hidden"
          >
            {/* Source Header */}
            <div className="p-5 border-b border-gray-100">
              <div className="flex items-center gap-2 mb-3">
                <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                  {source.insight_count} insight{source.insight_count !== 1 ? 's' : ''}
                </span>
                <span className="text-xs text-gray-500">
                  {new Date(source.created_at).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                  })}
                </span>
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-3">
                {source.title}
              </h2>
              
              {/* Source Link */}
              <a 
                href={source.source_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center text-sm text-blue-600 hover:text-blue-800 hover:underline transition"
              >
                <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                {source.source_domain}
                <svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>

            {/* Insights List */}
            <div className="p-5 space-y-5">
              {source.insights && source.insights.length > 0 ? (
                source.insights.map((insight) => {
                  // Split into category line and insight text
                  const lines = insight.text.split('\n');
                  const categoryLine = lines[0];
                  const insightText = lines.slice(1).join('\n');
                  
                  return (
                    <div key={insight.id} className="space-y-1.5">
                      {/* Category Badge */}
                      <div className="text-xs font-bold text-gray-500 tracking-wide">
                        {categoryLine}
                      </div>
                      {/* Insight Text */}
                      <p className="text-sm text-gray-800 leading-relaxed">
                        {insightText || insight.text}
                      </p>
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-gray-500">No insights available</p>
              )}
            </div>

            {/* Actions */}
            <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
              <div className="flex gap-3">
                {/* Like Button - X.com style */}
                <button
                  onClick={() => handleEngagement(source.id, 'like')}
                  className="group flex items-center gap-1.5 text-gray-500 hover:text-pink-600 transition-colors"
                  title={likedInsights.has(source.id) ? 'Unlike' : 'Like'}
                >
                  {likedInsights.has(source.id) ? (
                    <svg className="w-5 h-5 text-pink-600" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 group-hover:text-pink-600" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                  )}
                </button>

                {/* Bookmark Button - X.com style */}
                <button
                  onClick={() => handleEngagement(source.id, 'bookmark')}
                  className="group flex items-center gap-1.5 text-gray-500 hover:text-blue-600 transition-colors"
                  title={bookmarkedInsights.has(source.id) ? 'Remove bookmark' : 'Bookmark'}
                >
                  {bookmarkedInsights.has(source.id) ? (
                    <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 group-hover:text-blue-600" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
                    </svg>
                  )}
                </button>
              </div>
              <button
                onClick={() => handleEngagement(source.id, 'x')}
                className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition"
                title="Not interested"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
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
