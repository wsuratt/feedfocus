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
  const [engagedInsights, setEngagedInsights] = useState<Set<string>>(new Set());
  const [showSuggestions, setShowSuggestions] = useState(false);

  // API URL from environment or default to localhost
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    loadInterests();
    loadFeed();
  }, []);

  const loadInterests = async () => {
    try {
      const response = await fetch(`${API_URL}/api/interests`);
      const data = await response.json();
      setInterests(data);
      setShowSuggestions(data.length === 0);
    } catch (error) {
      console.error('Failed to load interests:', error);
    }
  };

  const loadFeed = async () => {
    try {
      const response = await fetch(`${API_URL}/api/feed?limit=50`);
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
      await fetch(`${API_URL}/api/interests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: newInterest })
      });
      
      setNewInterest('');
      await loadInterests();
      await loadFeed(); // Refresh feed with new interest
    } catch (error) {
      console.error('Failed to add interest:', error);
    }
  };

  const deleteInterest = async (id: number) => {
    try {
      await fetch(`${API_URL}/api/interests/${id}`, {
        method: 'DELETE'
      });
      await loadInterests();
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

    // If action is 'x', remove card from view immediately
    if (action === 'x') {
      setSources(sources.filter(source => source.id !== insightId));
    } else {
      // Mark as engaged locally for visual feedback
      setEngagedInsights(new Set(engagedInsights).add(insightId));
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with Interests Management */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Insight Feed</h1>
          
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
              <div className="flex gap-2">
                <button
                  onClick={() => handleEngagement(source.id, 'like')}
                  className={`px-4 py-2 rounded-lg font-medium text-sm transition ${
                    engagedInsights.has(source.id)
                      ? 'bg-green-50 text-green-600 border border-green-200'
                      : 'bg-white text-gray-700 border border-gray-200 hover:bg-green-50 hover:border-green-200'
                  }`}
                >
                  ❤️ Like
                </button>
                <button
                  onClick={() => handleEngagement(source.id, 'bookmark')}
                  className="px-4 py-2 bg-white text-gray-700 border border-gray-200 rounded-lg font-medium text-sm hover:bg-gray-50 transition"
                >
                  🔖 Save
                </button>
              </div>
              <button
                onClick={() => handleEngagement(source.id, 'x')}
                className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                title="Dismiss this card"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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
