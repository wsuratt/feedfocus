import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';

// Unified Feed Types
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
  score?: number;
  predicted_score?: number;
}

interface FeedResponse {
  feed_type: 'following' | 'for_you';
  insights: UnifiedInsight[];
  count: number;
  has_more: boolean;
}

type FeedType = 'following' | 'for_you';
type EngagementAction = 'view' | 'like' | 'save' | 'dismiss';

export function UnifiedFeed() {
  // Tab state
  const [activeTab, setActiveTab] = useState<FeedType>('for_you');

  // Feed data
  const [insights, setInsights] = useState<UnifiedInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);

  // Engagement state
  const [likedInsights, setLikedInsights] = useState<Set<string>>(new Set());
  const [savedInsights, setSavedInsights] = useState<Set<string>>(new Set());
  const [dismissedInsights, setDismissedInsights] = useState<Set<string>>(new Set());
  const [followedTopics, setFollowedTopics] = useState<Set<string>>(new Set());

  // Infinite scroll
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();
  const { user, getAccessToken } = useAuth();
  const API_URL = import.meta.env.VITE_API_URL || '';
  const LIMIT = 30;

  // Load initial feed
  useEffect(() => {
    loadEngagements();
    loadFollowedTopics();
    loadFeed(true);
  }, [activeTab]);

  // Setup infinite scroll observer
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect();

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingMore && hasMore) {
          loadFeed(false);
        }
      },
      { threshold: 0.1 }
    );

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [loadingMore, hasMore, offset, activeTab]);

  // Load engagement state from localStorage
  const loadEngagements = () => {
    try {
      const liked = localStorage.getItem('likedInsights');
      const saved = localStorage.getItem('savedInsights');
      const dismissed = localStorage.getItem('dismissedInsights');

      if (liked) setLikedInsights(new Set(JSON.parse(liked)));
      if (saved) setSavedInsights(new Set(JSON.parse(saved)));
      if (dismissed) setDismissedInsights(new Set(JSON.parse(dismissed)));
    } catch (error) {
      console.error('Failed to load engagements:', error);
    }
  };

  // Save engagement state to localStorage
  const saveEngagements = () => {
    try {
      localStorage.setItem('likedInsights', JSON.stringify([...likedInsights]));
      localStorage.setItem('savedInsights', JSON.stringify([...savedInsights]));
      localStorage.setItem('dismissedInsights', JSON.stringify([...dismissedInsights]));
    } catch (error) {
      console.error('Failed to save engagements:', error);
    }
  };

  // Load followed topics from API
  const loadFollowedTopics = async () => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const response = await fetch(`${API_URL}/api/topics/following`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setFollowedTopics(new Set(data.topics || []));
      }
    } catch (error) {
      console.error('Failed to load followed topics:', error);
    }
  };

  // Follow/unfollow a topic
  const handleFollowTopic = async (topic: string) => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const isFollowing = followedTopics.has(topic);
      const method = isFollowing ? 'DELETE' : 'POST';

      const response = await fetch(`${API_URL}/api/topics/follow`, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic }),
      });

      if (response.ok) {
        setFollowedTopics(prev => {
          const newSet = new Set(prev);
          if (isFollowing) {
            newSet.delete(topic);
          } else {
            newSet.add(topic);
          }
          return newSet;
        });
      }
    } catch (error) {
      console.error('Failed to follow/unfollow topic:', error);
    }
  };

  // Load feed from API
  const loadFeed = async (reset: boolean = false) => {
    if (reset) {
      setLoading(true);
      setOffset(0);
    } else {
      setLoadingMore(true);
    }

    try {
      const currentOffset = reset ? 0 : offset;
      const endpoint = activeTab === 'following'
        ? `/api/feed/following`
        : `/api/feed/for-you`;

      // Get auth token
      const token = await getAccessToken();

      const response = await fetch(
        `${API_URL}${endpoint}?limit=${LIMIT}&offset=${currentOffset}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: FeedResponse = await response.json();

      // Filter out dismissed insights
      const filteredInsights = data.insights.filter(
        insight => !dismissedInsights.has(insight.id)
      );

      if (reset) {
        setInsights(filteredInsights);
      } else {
        setInsights(prev => [...prev, ...filteredInsights]);
      }

      setHasMore(data.has_more);
      setOffset(currentOffset + filteredInsights.length);
    } catch (error) {
      console.error('Failed to load feed:', error);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // Handle engagement
  const handleEngagement = async (insightId: string, action: EngagementAction) => {
    // Record with backend
    try {
      const token = await getAccessToken();

      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          insight_id: insightId,
          action,
        }),
      });
    } catch (error) {
      console.error('Failed to record engagement:', error);
    }

    // Update local state
    if (action === 'like') {
      const newLiked = new Set(likedInsights);
      if (newLiked.has(insightId)) {
        newLiked.delete(insightId);
      } else {
        newLiked.add(insightId);
      }
      setLikedInsights(newLiked);
    } else if (action === 'save') {
      const newSaved = new Set(savedInsights);
      if (newSaved.has(insightId)) {
        newSaved.delete(insightId);
      } else {
        newSaved.add(insightId);
      }
      setSavedInsights(newSaved);
    } else if (action === 'dismiss') {
      const newDismissed = new Set(dismissedInsights);
      newDismissed.add(insightId);
      setDismissedInsights(newDismissed);

      // Remove from current list
      setInsights(prev => prev.filter(i => i.id !== insightId));
    }

    saveEngagements();
  };

  // Category badge colors
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

  // Render insight card
  const renderInsightCard = (insight: UnifiedInsight, index: number) => (
    <motion.div
      key={insight.id}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow"
    >
      {/* Topic Tag with Follow Button */}
      <div className="mb-3 flex items-center justify-between">
        <span className="inline-block px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-sm font-medium">
          #{insight.topic}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleFollowTopic(insight.topic);
          }}
          className={`px-3 py-1 text-xs font-medium rounded-full transition ${
            followedTopics.has(insight.topic)
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          {followedTopics.has(insight.topic) ? 'Following' : 'Follow Topic'}
        </button>
      </div>

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
      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <div className="flex items-center gap-4">
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

        {/* Dismiss Button */}
        <button
          onClick={() => handleEngagement(insight.id, 'dismiss')}
          className="text-gray-400 hover:text-gray-600 transition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </motion.div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex items-center justify-between py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Feed Focus
            </h1>
            <button
              onClick={() => navigate('/profile')}
              className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-bold hover:bg-blue-700 transition"
              title="View Profile"
            >
              {user?.email?.[0].toUpperCase() || 'U'}
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1">
            <button
              onClick={() => {
                setActiveTab('for_you');
                setInsights([]);
              }}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${
                activeTab === 'for_you'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              For You
            </button>
            <button
              onClick={() => {
                setActiveTab('following');
                setInsights([]);
              }}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${
                activeTab === 'following'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              Following
            </button>
          </div>
        </div>
      </div>

      {/* Feed Content */}
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Loading State */}
        {loading && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin mb-4"></div>
            <p className="text-gray-600">Loading insights...</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && insights.length === 0 && (
          <div className="text-center py-16">
            <div className="text-6xl mb-4">📱</div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">
              {activeTab === 'following' ? 'No insights yet' : 'Discover new topics'}
            </h2>
            <p className="text-gray-600">
              {activeTab === 'following'
                ? 'Follow some topics to see insights here'
                : 'Explore insights from topics you might like'}
            </p>
          </div>
        )}

        {/* Insights */}
        {!loading && insights.length > 0 && (
          <div className="space-y-4">
            {insights.map((insight, index) => renderInsightCard(insight, index))}
          </div>
        )}

        {/* Load More Trigger */}
        {hasMore && !loading && (
          <div ref={loadMoreRef} className="py-8 text-center">
            {loadingMore && (
              <div className="inline-block w-6 h-6 border-3 border-blue-100 border-t-blue-600 rounded-full animate-spin"></div>
            )}
          </div>
        )}

        {/* End of Feed */}
        {!hasMore && insights.length > 0 && (
          <div className="py-8 text-center text-gray-500 text-sm">
            You've reached the end! 🎉
          </div>
        )}
      </div>
    </div>
  );
}
