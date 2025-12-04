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
  const [followedTopics, setFollowedTopics] = useState<string[]>([]);
  const [likedInsights, setLikedInsights] = useState<UnifiedInsight[]>([]);
  const [savedInsights, setSavedInsights] = useState<UnifiedInsight[]>([]);
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
        setFollowedTopics(data.topics || []);
      }
    } catch (error) {
      console.error('Failed to load followed topics:', error);
    }
  };

  const loadLocalEngagements = () => {
    try {
      const liked = localStorage.getItem('likedInsights');
      const saved = localStorage.getItem('savedInsights');
      
      // For now, just show counts - in production, you'd fetch full insight details from backend
      if (liked) {
        // TODO: Fetch full insight details from backend using these IDs
        // const likedIds = JSON.parse(liked);
        setLikedInsights([]);
      }
      
      if (saved) {
        // TODO: Fetch full insight details from backend using these IDs
        // const savedIds = JSON.parse(saved);
        setSavedInsights([]);
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
        setFollowedTopics(prev => prev.filter(t => t !== topic));
      }
    } catch (error) {
      console.error('Failed to unfollow topic:', error);
    }
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
                {followedTopics.length} topics following
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
                    {likedInsights.map((insight) => (
                      <motion.div
                        key={insight.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="p-4 border rounded-lg hover:border-blue-300 transition cursor-pointer"
                        onClick={() => window.open(insight.source_url, '_blank')}
                      >
                        <p className="text-gray-900 mb-2">{insight.text}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs">
                            {insight.topic}
                          </span>
                          <span>•</span>
                          <span>{insight.source_domain}</span>
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
                    {savedInsights.map((insight) => (
                      <motion.div
                        key={insight.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="p-4 border rounded-lg hover:border-blue-300 transition cursor-pointer"
                        onClick={() => window.open(insight.source_url, '_blank')}
                      >
                        <p className="text-gray-900 mb-2">{insight.text}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs">
                            {insight.topic}
                          </span>
                          <span>•</span>
                          <span>{insight.source_domain}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'topics' && (
              <div>
                {followedTopics.length === 0 ? (
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
                    {followedTopics.map((topic) => (
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
