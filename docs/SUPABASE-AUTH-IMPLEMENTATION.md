# Supabase Authentication Implementation Plan

## 📋 Overview

**Objective:** Add user authentication to Feed Focus using Supabase Auth, replacing the hardcoded `user_id="default"` with real user accounts.

**Current State:**
- ✅ Backend: FastAPI accepts `user_id` parameter on all endpoints
- ✅ Mobile: Axios API client with hardcoded `userId='default'`
- ✅ Web: Fetch API calls with hardcoded `USER_ID='default'`
- ✅ SQLite database with user-specific tables (`user_topics`, `user_engagement`)

**Target State:**
- 🎯 Users can sign up/login (email/password + OAuth)
- 🎯 Backend validates JWT tokens from Supabase
- 🎯 Frontend apps send auth tokens with API requests
- 🎯 Real user IDs used throughout the system

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  SUPABASE (Auth Provider)                               │
│  • User management                                      │
│  • JWT token generation                                 │
│  • OAuth providers (Google, Apple, etc.)                │
└─────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
┌───────────────────┐              ┌───────────────────┐
│  WEB FRONTEND     │              │  MOBILE APP       │
│  React + Vite     │              │  React Native     │
│                   │              │                   │
│  • Login UI       │              │  • Login UI       │
│  • Session mgmt   │              │  • Session mgmt   │
│  • Token refresh  │              │  • Token refresh  │
└───────────────────┘              └───────────────────┘
        │                                   │
        │ JWT Token                         │ JWT Token
        └─────────────────┬─────────────────┘
                          ↓
        ┌─────────────────────────────────┐
        │  FASTAPI BACKEND                │
        │                                 │
        │  • JWT verification middleware  │
        │  • Extract user_id from token   │
        │  • Existing endpoints unchanged │
        └─────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────┐
        │  SQLITE DATABASE                │
        │                                 │
        │  • user_topics                  │
        │  • user_engagement              │
        │  • insights (shared)            │
        └─────────────────────────────────┘
```

---

## 📦 Phase 1: Supabase Setup

### 1.1 Create Supabase Project

```bash
# Go to https://supabase.com/dashboard
# 1. Create new project
# 2. Note down:
#    - Project URL
#    - Anon/Public Key
#    - Service Role Key (for backend)
```

### 1.2 Configure Authentication

**In Supabase Dashboard:**
- Enable Email/Password auth
- Enable Google OAuth (optional)
- Enable Apple OAuth (optional for iOS)
- Configure redirect URLs:
  - Web: `https://feed-focus.com`
  - Mobile: `feedfocus://auth/callback`

### 1.3 Environment Variables

Create `.env` files:

**Backend** (`/feedfocus/.env`):
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret
```

**Web** (`/feedfocus/frontend/.env`):
```bash
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_API_URL=https://api.feed-focus.com
```

**Mobile** (`/feedfocus-mobile/.env`):
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
API_BASE_URL=https://api.feed-focus.com
```

---

## 🔧 Phase 2: Backend Implementation

### 2.1 Install Dependencies

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus
pip install supabase python-jose[cryptography]
```

### 2.2 Create Auth Middleware

**File:** `/feedfocus/backend/middleware/auth.py`

```python
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os

security = HTTPBearer()

SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify Supabase JWT token and return user_id
    
    Returns:
        user_id (str): Supabase user ID from token
    """
    token = credentials.credentials
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=['HS256'],
            audience='authenticated'
        )
        
        # Extract user ID (Supabase uses 'sub' claim)
        user_id = payload.get('sub')
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        
        return user_id
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
```

### 2.3 Update Endpoints

**File:** `/feedfocus/backend/main.py`

```python
from backend.middleware.auth import verify_token
from fastapi import Depends

# Update unified feed endpoints to use auth
@app.get("/api/feed/following")
async def get_following_feed(
    limit: int = 30,
    offset: int = 0,
    user_id: str = Depends(verify_token)  # Extract from JWT
):
    """Get Following feed - now requires authentication"""
    feed_service = FeedService()
    insights = feed_service.generate_following_feed(user_id, limit, offset)
    
    return {
        "feed_type": "following",
        "insights": insights,
        "count": len(insights),
        "has_more": len(insights) == limit
    }

# Similar updates for:
# - /api/feed/for-you
# - /api/feed/engage
# - /api/topics/follow
# - /api/topics/following
```

### 2.4 Optional Public Endpoints

Keep some endpoints public for demo/testing:

```python
# Optional: Allow unauthenticated access with default user
@app.get("/api/feed/following/demo")
async def get_following_feed_demo(limit: int = 30, offset: int = 0):
    """Public demo endpoint - no auth required"""
    user_id = "demo_user"
    feed_service = FeedService()
    insights = feed_service.generate_following_feed(user_id, limit, offset)
    return {"feed_type": "following", "insights": insights}
```

---

## 💻 Phase 3: Web Frontend Implementation

### 3.1 Install Dependencies

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus/frontend
npm install @supabase/supabase-js
```

### 3.2 Create Supabase Client

**File:** `/feedfocus/frontend/src/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

### 3.3 Create Auth Context

**File:** `/feedfocus/frontend/src/contexts/AuthContext.tsx`

```typescript
import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import type { User, Session } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  };

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    });
    if (error) throw error;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const getAccessToken = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      session, 
      loading, 
      signIn, 
      signUp, 
      signOut,
      getAccessToken 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

### 3.4 Create Login Component

**File:** `/feedfocus/frontend/src/components/Login.tsx`

```typescript
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState('');
  const { signIn, signUp } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      if (isSignUp) {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-3xl font-bold text-center">
            {isSignUp ? 'Sign Up' : 'Sign In'}
          </h2>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg"
              required
            />
          </div>
          
          <div>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg"
              required
            />
          </div>

          {error && (
            <div className="text-red-500 text-sm">{error}</div>
          )}

          <button
            type="submit"
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            {isSignUp ? 'Sign Up' : 'Sign In'}
          </button>
        </form>

        <div className="text-center">
          <button
            onClick={() => setIsSignUp(!isSignUp)}
            className="text-blue-600 hover:underline"
          >
            {isSignUp ? 'Already have an account? Sign in' : 'Need an account? Sign up'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 3.5 Update App.tsx

**File:** `/feedfocus/frontend/src/App.tsx`

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { UnifiedFeed } from './components/UnifiedFeed';
import { Login } from './components/Login';
import './App.css';

function ProtectedApp() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!user) {
    return <Login />;
  }

  return <UnifiedFeed />;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProtectedApp />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
```

### 3.6 Update API Calls in UnifiedFeed

**File:** `/feedfocus/frontend/src/components/UnifiedFeed.tsx`

```typescript
import { useAuth } from '../contexts/AuthContext';

export function UnifiedFeed() {
  const { getAccessToken, user } = useAuth();
  const USER_ID = user?.id || 'default';

  // Update loadFeed function
  const loadFeed = async (reset: boolean = false) => {
    setLoading(reset);
    setLoadingMore(!reset);

    try {
      // Get auth token
      const token = await getAccessToken();
      
      const endpoint = activeTab === 'following' 
        ? '/api/feed/following' 
        : '/api/feed/for-you';
      
      const url = `${API_URL}${endpoint}?limit=${LIMIT}&offset=${reset ? 0 : offset}`;
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,  // Add auth header
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to fetch feed');

      const data: FeedResponse = await response.json();
      
      // ... rest of logic
    } catch (error) {
      console.error('Error loading feed:', error);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // Update recordEngagement function
  const recordEngagement = async (insightId: string, action: EngagementAction) => {
    try {
      const token = await getAccessToken();
      
      await fetch(`${API_URL}/api/feed/engage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: USER_ID,
          insight_id: insightId,
          action,
        }),
      });
    } catch (error) {
      console.error('Failed to record engagement:', error);
    }
  };
}
```

---

## 📱 Phase 4: Mobile App Implementation

### 4.1 Install Dependencies

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus-mobile
npm install @supabase/supabase-js
npx expo install expo-secure-store expo-crypto
```

### 4.2 Create Supabase Client

**File:** `/feedfocus-mobile/src/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js';
import * as SecureStore from 'expo-secure-store';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from '@env';

// Custom storage adapter for React Native
const ExpoSecureStoreAdapter = {
  getItem: (key: string) => {
    return SecureStore.getItemAsync(key);
  },
  setItem: (key: string, value: string) => {
    SecureStore.setItemAsync(key, value);
  },
  removeItem: (key: string) => {
    SecureStore.deleteItemAsync(key);
  },
};

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: ExpoSecureStoreAdapter as any,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
```

### 4.3 Create Auth Context

**File:** `/feedfocus-mobile/src/contexts/AuthContext.tsx`

```typescript
import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import type { User, Session } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  };

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    });
    if (error) throw error;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const getAccessToken = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      session, 
      loading, 
      signIn, 
      signUp, 
      signOut,
      getAccessToken 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

### 4.4 Create Login Screen

**File:** `/feedfocus-mobile/src/screens/Login.tsx`

```typescript
import { useState } from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet, Alert } from 'react-native';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const { signIn, signUp } = useAuth();

  const handleSubmit = async () => {
    try {
      if (isSignUp) {
        await signUp(email, password);
        Alert.alert('Success', 'Account created! Please check your email to verify.');
      } else {
        await signIn(email, password);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{isSignUp ? 'Sign Up' : 'Sign In'}</Text>
      
      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />
      
      <TextInput
        style={styles.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity style={styles.button} onPress={handleSubmit}>
        <Text style={styles.buttonText}>
          {isSignUp ? 'Sign Up' : 'Sign In'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity onPress={() => setIsSignUp(!isSignUp)}>
        <Text style={styles.link}>
          {isSignUp ? 'Already have an account? Sign in' : 'Need an account? Sign up'}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 40,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 15,
    marginBottom: 15,
    borderRadius: 8,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 8,
    marginTop: 10,
  },
  buttonText: {
    color: '#fff',
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '600',
  },
  link: {
    color: '#007AFF',
    textAlign: 'center',
    marginTop: 20,
  },
});
```

### 4.5 Update App.tsx

**File:** `/feedfocus-mobile/App.tsx`

```typescript
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from './src/contexts/AuthContext';
import { UnifiedFeed } from './src/screens/UnifiedFeed';
import { Login } from './src/screens/Login';
import { View, ActivityIndicator } from 'react-native';

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <>
      {user ? <UnifiedFeed /> : <Login />}
      <StatusBar style="dark" />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
```

### 4.6 Update API Service

**File:** `/feedfocus-mobile/src/services/api.ts`

```typescript
import axios from 'axios';
import { SourceCard, FeedResponse, FeedType, EngagementAction } from '../types';
import { API_BASE_URL } from '@env';
import { supabase } from '../lib/supabase';

const BASE_URL = API_BASE_URL || 'https://api.feed-focus.com';

// Create axios instance without default headers
const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
});

// Add request interceptor to attach auth token
apiClient.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession();
  
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  
  config.headers['Content-Type'] = 'application/json';
  
  return config;
});

export const api = {
  /**
   * Get Following feed - insights from user's followed topics
   */
  async getFollowingFeed(
    limit: number = 30,
    offset: number = 0
  ): Promise<FeedResponse> {
    try {
      const response = await apiClient.get('/api/feed/following', {
        params: { limit, offset },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch Following feed:', error);
      throw error;
    }
  },

  /**
   * Get For You feed - algorithmic recommendations
   */
  async getForYouFeed(
    limit: number = 30,
    offset: number = 0
  ): Promise<FeedResponse> {
    try {
      const response = await apiClient.get('/api/feed/for-you', {
        params: { limit, offset },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch For You feed:', error);
      throw error;
    }
  },

  /**
   * Record engagement with unified feed insight
   */
  async recordUnifiedEngagement(
    insightId: string,
    action: EngagementAction
  ): Promise<void> {
    try {
      await apiClient.post('/api/feed/engage', {
        insight_id: insightId,
        action,
      });
    } catch (error) {
      console.error('Failed to record engagement:', error);
    }
  },

  // ... other methods
};
```

### 4.7 Update env.d.ts

**File:** `/feedfocus-mobile/src/env.d.ts`

```typescript
declare module '@env' {
  export const API_BASE_URL: string;
  export const SUPABASE_URL: string;
  export const SUPABASE_ANON_KEY: string;
}
```

---

## ✅ Phase 5: Testing Plan

### 5.1 Backend Testing

```bash
# Test token verification
curl -X GET https://api.feed-focus.com/api/feed/following \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json"

# Expected: 200 OK with feed data
# Without token: 401 Unauthorized
```

### 5.2 Web Testing

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus/frontend
npm run dev

# Test flow:
# 1. Sign up new account
# 2. Verify email
# 3. Sign in
# 4. Check feed loads
# 5. Like/save insights
# 6. Sign out
# 7. Sign in again - check persisted state
```

### 5.3 Mobile Testing

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus-mobile
npx expo start

# Test flow:
# 1. Sign up
# 2. Verify email
# 3. Sign in
# 4. Check feed loads
# 5. Engagement tracking works
# 6. Close app
# 7. Reopen - still logged in
```

---

## 🚀 Phase 6: Deployment

### 6.1 Backend Deployment

```bash
# SERVER
ssh ubuntu@3.17.64.149
cd /home/ubuntu/feedfocus

# Add environment variables
echo "SUPABASE_URL=https://xxxxx.supabase.co" >> .env
echo "SUPABASE_SERVICE_KEY=eyJ..." >> .env
echo "SUPABASE_JWT_SECRET=your-secret" >> .env

# Install dependencies
pip install supabase python-jose[cryptography]

# Pull latest code
git pull origin main

# Restart backend
sudo systemctl restart feedfocus-backend
```

### 6.2 Web Deployment

```bash
# Update .env.production with Supabase keys
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus/frontend

# Build
npm run build

# Deploy to server
scp -r dist/* ubuntu@3.17.64.149:/app/frontend/dist/
```

### 6.3 Mobile Deployment

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus-mobile

# Update .env with production Supabase keys
# Build for production
npx eas build --platform ios --profile production
npx eas build --platform android --profile production

# Submit to stores
npx eas submit --platform ios
npx eas submit --platform android
```

---

## 📊 Migration Strategy

### Existing Users

For the single "default" user, create a migration:

```sql
-- Option 1: Keep existing data for a demo account
UPDATE user_topics SET user_id = 'demo_user' WHERE user_id = 'default';
UPDATE user_engagement SET user_id = 'demo_user' WHERE user_id = 'default';

-- Option 2: Delete anonymous data (start fresh)
DELETE FROM user_topics WHERE user_id = 'default';
DELETE FROM user_engagement WHERE user_id = 'default';
```

---

## 🔒 Security Considerations

1. **JWT Secret** - Store securely in environment variables
2. **HTTPS Only** - Enforce SSL for all API calls
3. **Token Refresh** - Supabase handles automatic refresh
4. **Rate Limiting** - Add rate limiting to login endpoints
5. **Email Verification** - Require email verification for signups

---

## 📈 Success Metrics

- ✅ Users can sign up/sign in
- ✅ Auth tokens sent with API requests
- ✅ Backend validates tokens correctly
- ✅ User data isolated per account
- ✅ Session persists across app restarts
- ✅ No breaking changes to existing feed logic

---

## 🎯 Timeline Estimate

- **Phase 1:** Supabase setup - 1 hour
- **Phase 2:** Backend implementation - 2 hours
- **Phase 3:** Web frontend - 3 hours
- **Phase 4:** Mobile app - 3 hours
- **Phase 5:** Testing - 2 hours
- **Phase 6:** Deployment - 1 hour

**Total: ~12 hours**

---

## 📚 Resources

- [Supabase Auth Docs](https://supabase.com/docs/guides/auth)
- [Supabase React Guide](https://supabase.com/docs/guides/getting-started/tutorials/with-react)
- [Supabase React Native Guide](https://supabase.com/docs/guides/getting-started/tutorials/with-react-native)
- [FastAPI + JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

---

**Ready to implement?** Start with Phase 1! 🚀
