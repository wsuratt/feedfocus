import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';

interface UnifiedInsight {
  id: string;
  topic: string;
  category: string;
  text: string;
  source_url: string;
  source_domain: string;
  quality_score: number;
  engagement_score: number;
  created_at: string;
}

interface TopicStatus {
  topic: string;
  is_following: boolean;
  insight_count: number;
  extraction_job?: {
    status: 'queued' | 'processing' | 'complete' | 'failed';
    insight_count: number;
    error?: any;
    sources_processed: number;
    estimated_completion_at?: string;
    retry_count: number;
  } | null;
}

interface FollowResponse {
  status: 'ready' | 'extracting' | 'invalid';
  topic?: string;
  original_topic?: string;
  insight_count?: number;
  similarity?: number;
  message?: string;
  error?: string;
  suggestion?: string;
  job_id?: string;
}

export function Search() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [following, setFollowing] = useState(false);
  const [topicStatus, setTopicStatus] = useState<TopicStatus | null>(null);
  const [followResponse, setFollowResponse] = useState<FollowResponse | null>(null);
  const [insights, setInsights] = useState<UnifiedInsight[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [likedInsights, setLikedInsights] = useState<Set<string>>(new Set());
  const [savedInsights, setSavedInsights] = useState<Set<string>>(new Set());

  const navigate = useNavigate();
  const { user, getAccessToken } = useAuth();
  const API_URL = import.meta.env.VITE_API_URL || '';

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!searchQuery.trim()) return;

    setSearching(true);
    setError(null);
    setTopicStatus(null);
    setFollowResponse(null);
    setHasSearched(true);

    try {
      const token = await getAccessToken();
      if (!token) {
        setError('Authentication required');
        return;
      }

      // Check topic status without following
      const response = await fetch(`${API_URL}/api/topics/${encodeURIComponent(searchQuery.trim())}/status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data: TopicStatus = await response.json();
        setTopicStatus(data);

        // Fetch insights if they exist
        if (data.insight_count > 0) {
          await fetchInsights(data.topic);
        } else {
          setInsights([]);
        }
      } else {
        // Topic doesn't exist yet - that's okay
        setTopicStatus({
          topic: searchQuery.trim(),
          is_following: false,
          insight_count: 0,
          extraction_job: null,
        });
        setInsights([]);
      }

    } catch (err) {
      console.error('Search error:', err);
      // Topic not found - ready to follow
      setTopicStatus({
        topic: searchQuery.trim(),
        is_following: false,
        insight_count: 0,
        extraction_job: null,
      });
      setInsights([]);
    } finally {
      setSearching(false);
    }
  };

  const fetchInsights = async (topic: string) => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const response = await fetch(
        `${API_URL}/api/topics/${encodeURIComponent(topic)}/insights?limit=20`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setInsights(data.insights || []);
      }
    } catch (err) {
      console.error('Failed to fetch insights:', err);
    }
  };

  const handleFollowTopic = async () => {
    if (!searchQuery.trim()) return;

    setFollowing(true);
    setError(null);

    try {
      const token = await getAccessToken();
      if (!token) {
        setError('Authentication required');
        return;
      }

      const response = await fetch(`${API_URL}/api/topics/follow`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic: searchQuery.trim() }),
      });

      const data: FollowResponse = await response.json();

      if (!response.ok) {
        setError(data.error || 'Failed to follow topic');
        return;
      }

      setFollowResponse(data);

      // Update topic status to reflect following
      if (topicStatus) {
        setTopicStatus({ ...topicStatus, is_following: true });
      }

      // If extraction started, insights will appear later
      if (data.status === 'extracting') {
        setInsights([]);
      }

      // If invalid, show error
      if (data.status === 'invalid') {
        setError(data.error || 'Invalid topic');
      }

    } catch (err) {
      console.error('Follow error:', err);
      setError('Failed to follow topic. Please try again.');
    } finally {
      setFollowing(false);
    }
  };

  const handleEngagement = async (insightId: string, action: 'like' | 'save') => {
    try {
      const token = await getAccessToken();
      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ insight_id: insightId, action }),
      });

      if (action === 'like') {
        setLikedInsights(prev => {
          const newSet = new Set(prev);
          if (newSet.has(insightId)) {
            newSet.delete(insightId);
          } else {
            newSet.add(insightId);
          }
          return newSet;
        });
      } else if (action === 'save') {
        setSavedInsights(prev => {
          const newSet = new Set(prev);
          if (newSet.has(insightId)) {
            newSet.delete(insightId);
          } else {
            newSet.add(insightId);
          }
          return newSet;
        });
      }
    } catch (err) {
      console.error('Failed to record engagement:', err);
    }
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'CASE STUDY': 'bg-purple-100 text-purple-700',
      'PLAYBOOK': 'bg-blue-100 text-blue-700',
      'TREND': 'bg-green-100 text-green-700',
      'COUNTERINTUITIVE': 'bg-orange-100 text-orange-700',
      'OPPORTUNITY': 'bg-yellow-100 text-yellow-700',
      'INSIGHT': 'bg-gray-100 text-gray-700',
    };
    return colors[category] || 'bg-gray-100 text-gray-700';
  };

  const renderStatusCard = () => {
    if (!hasSearched || !topicStatus) return null;

    // If we have a follow response, show that instead
    if (followResponse) return renderFollowResponse();

    const { topic, is_following, insight_count } = topicStatus;

    // Topic has insights and user is following
    if (insight_count > 0 && is_following) {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-green-50 border border-green-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-green-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 mb-1">Already Following</h3>
              <p className="text-green-700 text-sm mb-3">
                You're already following <span className="font-medium">#{topic}</span>
              </p>
              <div className="flex items-center gap-2 text-sm text-green-600 mb-3">
                <span className="px-2 py-1 bg-green-100 rounded font-medium">
                  {insight_count} insights available
                </span>
              </div>
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm font-medium"
              >
                View Insights
              </button>
            </div>
          </div>
        </motion.div>
      );
    }

    // Topic has insights but user is not following
    if (insight_count > 0 && !is_following) {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-blue-50 border border-blue-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-blue-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-blue-900 mb-1">Topic Found</h3>
              <p className="text-blue-700 text-sm mb-3">
                <span className="font-medium">#{topic}</span> has insights ready to view
              </p>
              <div className="flex items-center gap-2 text-sm text-blue-600 mb-3">
                <span className="px-2 py-1 bg-blue-100 rounded font-medium">
                  {insight_count} insights available
                </span>
              </div>
              <button
                onClick={handleFollowTopic}
                disabled={following}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {following ? 'Following...' : 'Follow Topic'}
              </button>
            </div>
          </div>
        </motion.div>
      );
    }

    // Topic has no insights
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-yellow-50 border border-yellow-200 rounded-xl p-6"
      >
        <div className="flex items-start gap-3">
          <svg className="w-6 h-6 text-yellow-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-900 mb-1">New Topic</h3>
            <p className="text-yellow-700 text-sm mb-3">
              No insights yet for <span className="font-medium">#{topic}</span>
            </p>
            <p className="text-yellow-600 text-xs mb-3">
              We'll gather insights from top sources (takes 2-3 minutes)
            </p>
            <button
              onClick={handleFollowTopic}
              disabled={following}
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition text-sm font-medium disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {following ? 'Following...' : 'Follow & Extract Insights'}
            </button>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderFollowResponse = () => {
    if (!followResponse) return null;

    const { status, topic, original_topic, insight_count, similarity, message, error: respError, suggestion } = followResponse;

    // Invalid topic
    if (status === 'invalid') {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50 border border-red-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 mb-1">Invalid Topic</h3>
              <p className="text-red-700 text-sm">{respError}</p>
              {suggestion && (
                <p className="text-red-600 text-sm mt-2">
                  <span className="font-medium">Suggestion:</span> {suggestion}
                </p>
              )}
            </div>
          </div>
        </motion.div>
      );
    }

    // Topic is ready (similar topic found)
    if (status === 'ready' && similarity !== undefined) {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-blue-50 border border-blue-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-blue-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-blue-900 mb-1">Similar Topic Found</h3>
              <p className="text-blue-700 text-sm mb-3">
                We found a very similar topic: <span className="font-medium">#{topic}</span>
              </p>
              <div className="flex items-center gap-2 text-sm text-blue-600 mb-3">
                <span className="px-2 py-1 bg-blue-100 rounded font-medium">
                  {insight_count} insights available
                </span>
                <span className="px-2 py-1 bg-blue-100 rounded font-medium">
                  {Math.round(similarity * 100)}% match
                </span>
              </div>
              {original_topic !== topic && (
                <p className="text-blue-600 text-xs italic mb-3">
                  Your search: "{original_topic}"
                </p>
              )}
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                View Insights
              </button>
            </div>
          </div>
        </motion.div>
      );
    }

    // Topic is ready (exact match)
    if (status === 'ready') {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-green-50 border border-green-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-green-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 mb-1">Topic Ready</h3>
              <p className="text-green-700 text-sm mb-3">
                You're now following <span className="font-medium">#{topic}</span>
              </p>
              <div className="flex items-center gap-2 text-sm text-green-600 mb-3">
                <span className="px-2 py-1 bg-green-100 rounded font-medium">
                  {insight_count} insights available
                </span>
              </div>
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm font-medium"
              >
                View Insights
              </button>
            </div>
          </div>
        </motion.div>
      );
    }

    // Extraction in progress
    if (status === 'extracting') {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-yellow-50 border border-yellow-200 rounded-xl p-6"
        >
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-yellow-500 flex-shrink-0 mt-0.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <div className="flex-1">
              <h3 className="font-semibold text-yellow-900 mb-1">Extraction in Progress</h3>
              <p className="text-yellow-700 text-sm mb-3">
                {message || 'We\'re gathering insights for'} <span className="font-medium">#{topic}</span>
              </p>
              <p className="text-yellow-600 text-xs mb-3">
                This usually takes 2-3 minutes. You can check back shortly or we'll notify you when ready.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate('/')}
                  className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition text-sm font-medium"
                >
                  Back to Feed
                </button>
                <button
                  onClick={() => {
                    setSearchQuery('');
                    setFollowResponse(null);
                  }}
                  className="px-4 py-2 bg-white border border-yellow-300 text-yellow-700 rounded-lg hover:bg-yellow-50 transition text-sm font-medium"
                >
                  Search Another Topic
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex items-center justify-between py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Search Topics
            </h1>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition"
              >
                Back to Feed
              </button>
              <button
                onClick={() => navigate('/profile')}
                className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-bold hover:bg-blue-700 transition"
                title="View Profile"
              >
                {user?.email?.[0].toUpperCase() || 'U'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Search Form */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <form onSubmit={handleSearch}>
            <div className="mb-4">
              <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
                What topic interests you?
              </label>
              <input
                id="search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g., AI agents, product-led growth, remote work"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                disabled={searching}
              />
              <p className="mt-2 text-xs text-gray-500">
                We'll search for existing insights or start gathering new ones for you.
              </p>
            </div>
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
            >
              {searching ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Searching...
                </span>
              ) : (
                'Search Topic'
              )}
            </button>
          </form>
        </div>

        {/* Error */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6"
          >
            <div className="flex items-center gap-2 text-red-800">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium">{error}</p>
            </div>
          </motion.div>
        )}

        {/* Status/Result */}
        {renderStatusCard()}

        {/* Insights */}
        {insights.length > 0 && (
          <div className="mt-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Insights for #{topicStatus?.topic}
            </h2>
            <div className="space-y-4">
              {insights.map((insight, index) => (
                <motion.div
                  key={insight.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.03 }}
                  className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow"
                >
                  {/* Category Badge */}
                  <div className="mb-3">
                    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold uppercase tracking-wide ${getCategoryColor(insight.category)}`}>
                      {insight.category}
                    </span>
                  </div>

                  {/* Insight Text */}
                  <p className="text-gray-900 text-base leading-relaxed mb-4">
                    {insight.text}
                  </p>

                  {/* Source */}
                  <a
                    href={insight.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 mb-4"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    {insight.source_domain}
                  </a>

                  {/* Actions */}
                  <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                    {/* Like Button */}
                    <button
                      onClick={() => handleEngagement(insight.id, 'like')}
                      className="flex items-center gap-2 text-gray-600 hover:text-pink-600 transition"
                    >
                      <svg
                        className={`w-5 h-5 ${likedInsights.has(insight.id) ? 'fill-pink-600 text-pink-600' : 'fill-none'}`}
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                      </svg>
                      <span className="text-sm">{likedInsights.has(insight.id) ? 'Liked' : 'Like'}</span>
                    </button>

                    {/* Save Button */}
                    <button
                      onClick={() => handleEngagement(insight.id, 'save')}
                      className="flex items-center gap-2 text-gray-600 hover:text-blue-600 transition"
                    >
                      <svg
                        className={`w-5 h-5 ${savedInsights.has(insight.id) ? 'fill-blue-600 text-blue-600' : 'fill-none'}`}
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                      </svg>
                      <span className="text-sm">{savedInsights.has(insight.id) ? 'Saved' : 'Save'}</span>
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Help Section */}
        {!hasSearched && (
          <div className="mt-8 bg-blue-50 border border-blue-100 rounded-xl p-6">
            <h3 className="font-semibold text-blue-900 mb-3">How it works</h3>
            <ul className="space-y-2 text-sm text-blue-800">
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Search for any topic you want to follow</span>
              </li>
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>We'll check if similar topics already exist with insights</span>
              </li>
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>If it's new, we'll start gathering insights automatically</span>
              </li>
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>You'll be following the topic and see insights in your feed</span>
              </li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
