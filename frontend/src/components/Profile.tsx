import { useState, useEffect } from 'react';
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

export function Profile() {
  const navigate = useNavigate();
  const { user, getAccessToken, signOut } = useAuth();
  const API_URL = import.meta.env.VITE_API_URL || '';

  const [activeTab, setActiveTab] = useState<'likes' | 'bookmarks' | 'topics'>('likes');
  const [followedTopics, setFollowedTopics] = useState<Set<string>>(new Set());
  const [likedInsights, setLikedInsights] = useState<UnifiedInsight[]>([]);
  const [savedInsights, setSavedInsights] = useState<UnifiedInsight[]>([]);
  const [likedSet, setLikedSet] = useState<Set<string>>(new Set());
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProfileData();
  }, []);

  const loadProfileData = async () => {
    setLoading(true);
    try {
      // Load followed topics from backend
      await loadFollowedTopics();
      
      // Load liked and saved insights from localStorage
      loadLocalEngagements();
    } catch (error) {
      console.error('Failed to load profile data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadFollowedTopics = async () => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const response = await fetch(`${API_URL}/api/topics/following`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
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

  const loadLocalEngagements = async () => {
    try {
      const token = await getAccessToken();
      if (!token) return;
      
      // Fetch liked insights
      const likedResponse = await fetch(`${API_URL}/api/insights/liked`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (likedResponse.ok) {
        const likedData = await likedResponse.json();
        const insights = likedData.insights || [];
        setLikedInsights(insights);
        setLikedSet(new Set(insights.map((i: UnifiedInsight) => i.id)));
      }
      
      // Fetch bookmarked insights
      const bookmarkedResponse = await fetch(`${API_URL}/api/insights/bookmarked`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (bookmarkedResponse.ok) {
        const bookmarkedData = await bookmarkedResponse.json();
        const insights = bookmarkedData.insights || [];
        setSavedInsights(insights);
        setSavedSet(new Set(insights.map((i: UnifiedInsight) => i.id)));
      }
    } catch (error) {
      console.error('Failed to load engagements:', error);
    }
  };

  const handleUnfollowTopic = async (topic: string) => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const response = await fetch(`${API_URL}/api/topics/follow`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ topic }),
      });

      if (response.ok) {
        setFollowedTopics(prev => {
          const newSet = new Set(prev);
          newSet.delete(topic);
          return newSet;
        });
      }
    } catch (error) {
      console.error('Failed to unfollow topic:', error);
    }
  };

  const handleFollowTopic = async (topic: string) => {
    try {
      const token = await getAccessToken();
      if (!token) return;

      const isFollowing = followedTopics.has(topic);
      const method = isFollowing ? 'DELETE' : 'POST';

      const response = await fetch(`${API_URL}/api/topics/follow`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
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

  const handleEngagement = async (insightId: string, action: 'like' | 'save') => {
    try {
      const token = await getAccessToken();
      if (!token) return;

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

      // Update local state
      if (action === 'like') {
        setLikedSet(prev => {
          const newSet = new Set(prev);
          if (newSet.has(insightId)) {
            newSet.delete(insightId);
            setLikedInsights(curr => curr.filter(i => i.id !== insightId));
          } else {
            newSet.add(insightId);
          }
          return newSet;
        });
      } else if (action === 'save') {
        setSavedSet(prev => {
          const newSet = new Set(prev);
          if (newSet.has(insightId)) {
            newSet.delete(insightId);
            setSavedInsights(curr => curr.filter(i => i.id !== insightId));
          } else {
            newSet.add(insightId);
          }
          return newSet;
        });
      }
    } catch (error) {
      console.error('Failed to record engagement:', error);
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

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate('/')}
              className="text-gray-600 hover:text-gray-900 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              <span>Back to Feed</span>
            </button>
            <h1 className="text-xl font-bold text-gray-900">Profile</h1>
            <button
              onClick={handleSignOut}
              className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* User Info */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
              {user?.email?.[0].toUpperCase() || 'U'}
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">{user?.email}</h2>
              <p className="text-sm text-gray-600 mt-1">
                {followedTopics.size} topics following
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-xl shadow-sm mb-6">
          <div className="flex border-b">
            <button
              onClick={() => setActiveTab('likes')}
              className={`flex-1 py-4 text-sm font-medium border-b-2 transition flex items-center justify-center gap-2 ${
                activeTab === 'likes'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
              Likes
            </button>
            <button
              onClick={() => setActiveTab('bookmarks')}
              className={`flex-1 py-4 text-sm font-medium border-b-2 transition flex items-center justify-center gap-2 ${
                activeTab === 'bookmarks'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Bookmarks
            </button>
            <button
              onClick={() => setActiveTab('topics')}
              className={`flex-1 py-4 text-sm font-medium border-b-2 transition flex items-center justify-center gap-2 ${
                activeTab === 'topics'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
              Topics
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'likes' && (
              <div>
                {likedInsights.length === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No likes yet</h3>
                    <p className="text-gray-600">
                      Insights you like will appear here
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {likedInsights.map((insight, index) => (
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
                        <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                          {/* Like Button */}
                          <button
                            onClick={() => handleEngagement(insight.id, 'like')}
                            className="flex items-center gap-2 text-gray-600 hover:text-pink-600 transition"
                          >
                            <svg
                              className={`w-5 h-5 ${likedSet.has(insight.id) ? 'fill-pink-600 text-pink-600' : 'fill-none'}`}
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                            <span className="text-sm">{likedSet.has(insight.id) ? 'Liked' : 'Like'}</span>
                          </button>

                          {/* Save Button */}
                          <button
                            onClick={() => handleEngagement(insight.id, 'save')}
                            className="flex items-center gap-2 text-gray-600 hover:text-blue-600 transition"
                          >
                            <svg
                              className={`w-5 h-5 ${savedSet.has(insight.id) ? 'fill-blue-600 text-blue-600' : 'fill-none'}`}
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                            </svg>
                            <span className="text-sm">{savedSet.has(insight.id) ? 'Saved' : 'Save'}</span>
                          </button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'bookmarks' && (
              <div>
                {savedInsights.length === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                    </svg>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No bookmarks yet</h3>
                    <p className="text-gray-600">
                      Save insights to read later
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {savedInsights.map((insight, index) => (
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
                        <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                          {/* Like Button */}
                          <button
                            onClick={() => handleEngagement(insight.id, 'like')}
                            className="flex items-center gap-2 text-gray-600 hover:text-pink-600 transition"
                          >
                            <svg
                              className={`w-5 h-5 ${likedSet.has(insight.id) ? 'fill-pink-600 text-pink-600' : 'fill-none'}`}
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                            <span className="text-sm">{likedSet.has(insight.id) ? 'Liked' : 'Like'}</span>
                          </button>

                          {/* Save Button */}
                          <button
                            onClick={() => handleEngagement(insight.id, 'save')}
                            className="flex items-center gap-2 text-gray-600 hover:text-blue-600 transition"
                          >
                            <svg
                              className={`w-5 h-5 ${savedSet.has(insight.id) ? 'fill-blue-600 text-blue-600' : 'fill-none'}`}
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                            </svg>
                            <span className="text-sm">{savedSet.has(insight.id) ? 'Saved' : 'Save'}</span>
                          </button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'topics' && (
              <div>
                {followedTopics.size === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No topics followed</h3>
                    <p className="text-gray-600">
                      Follow topics to customize your feed
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {Array.from(followedTopics).map((topic) => (
                      <motion.div
                        key={topic}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="flex items-center justify-between p-4 border rounded-lg hover:border-blue-300 transition"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                          </div>
                          <span className="font-medium text-gray-900">{topic}</span>
                        </div>
                        <button
                          onClick={() => handleUnfollowTopic(topic)}
                          className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition"
                        >
                          Unfollow
                        </button>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
