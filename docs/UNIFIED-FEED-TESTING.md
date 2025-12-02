# Unified Feed - Testing Guide

## 🎉 Implementation Complete!

All components of the unified feed are now built and ready for testing.

---

## ✅ What We Built

### Backend (Complete)
- ✅ New database tables (`insights`, `user_topics`, `user_engagement`)
- ✅ Feed service with ranking algorithm
- ✅ 6 new API endpoints
- ✅ Test data populated (9 insights, 3 topics)

### Mobile App (Complete)
- ✅ New unified feed screen with tabs
- ✅ Following & For You feeds
- ✅ Infinite scroll with pagination
- ✅ Topic tags on each insight
- ✅ Engagement tracking (like, save, dismiss)
- ✅ Pull-to-refresh
- ✅ Empty states

---

## 🧪 Testing Steps

### 1. Start Backend

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus

# Activate venv (if using)
source venv/bin/activate

# Start server
python backend/main.py
```

Server will run on `http://localhost:8000`

### 2. Start Mobile App

```bash
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus-mobile

# Start Expo
npx expo start
```

Then:
- Press `i` for iOS simulator
- Press `a` for Android emulator
- Or scan QR code with Expo Go on your phone

### 3. Test Following Feed

**Expected behavior:**
- Should show 6 insights (3 AI agents + 3 Value Investing)
- User is following: AI agents, Value Investing
- Each insight shows:
  - Topic tag (e.g., `#AI agents`)
  - Category badge (e.g., `CASE STUDY`)
  - Insight text
  - Source domain
  - Like, Save, Dismiss buttons

**Actions to test:**
- [ ] Pull to refresh
- [ ] Scroll down to trigger infinite scroll
- [ ] Tap heart icon to like
- [ ] Tap bookmark icon to save
- [ ] Tap X to dismiss (insight should disappear)
- [ ] Tap insight text to open source URL

### 4. Test For You Feed

**Expected behavior:**
- Should show ALL 9 insights (including Gen Z Consumer)
- Ranked by predicted engagement
- Same UI as Following feed

**Actions to test:**
- [ ] Switch to "For You" tab
- [ ] Verify all 3 topics appear
- [ ] Test engagement actions
- [ ] Scroll and load more

### 5. Test Persistence

**Actions:**
- Like 2-3 insights
- Save 2-3 insights
- Dismiss 1-2 insights
- Close app
- Reopen app

**Expected:**
- Liked insights still show pink hearts
- Saved insights still show blue bookmarks
- Dismissed insights don't reappear

### 6. Test API Endpoints

```bash
# Following feed
curl "http://localhost:8000/api/feed/following?user_id=default&limit=30&offset=0"

# For You feed
curl "http://localhost:8000/api/feed/for-you?user_id=default&limit=30&offset=0"

# Record engagement
curl -X POST http://localhost:8000/api/feed/engage \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default","insight_id":"<INSERT_ID>","action":"like"}'

# Get following topics
curl "http://localhost:8000/api/topics/following?user_id=default"

# Follow new topic
curl -X POST http://localhost:8000/api/topics/follow \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default","topic":"Gen Z Consumer"}'
```

---

## 🐛 Known Issues to Ignore

### TypeScript Lint Errors
These are **pre-existing configuration issues** and won't affect runtime:
- `Cannot use JSX unless the '--jsx' flag is provided`
- `Type 'Set<string>' can only be iterated through...`

Expo's Metro bundler handles JSX compilation independently. The app will run perfectly fine.

---

## 📱 Expected UI Behavior

### Tabs
- Two tabs: "Following" | "For You"
- Active tab has blue underline
- Switching tabs resets scroll and loads new feed

### Insight Cards
```
┌─────────────────────────────────────┐
│ #AI agents              [TAG]       │
│ CASE STUDY             [BADGE]      │
│                                     │
│ Duolingo grew from 40M to 100M...  │
│ The owl character became...         │
│                                     │
│ 🔗 anthropic.com                    │
│ ─────────────────────────────────── │
│ ♡  🔖                          ✕    │
└─────────────────────────────────────┘
```

### Infinite Scroll
- Load 30 insights initially
- Load more 30 when scrolling near bottom
- Show loading spinner at bottom while fetching
- Smooth, no jank

### Empty States
- "No insights yet" - Following feed when user has no topics
- "Discover new topics" - For You feed when empty

---

## 🎯 Success Criteria

### Performance
- [ ] Feed loads in < 2 seconds
- [ ] Scroll is smooth (60fps)
- [ ] No UI jank when loading more
- [ ] Pull-to-refresh feels responsive

### Functionality
- [ ] Both feeds load correct insights
- [ ] Tabs switch correctly
- [ ] Infinite scroll works
- [ ] Engagement persists
- [ ] Dismissed insights don't reappear

### UI/UX
- [ ] Topic tags are readable
- [ ] Category badges make sense
- [ ] Buttons are easy to tap
- [ ] Animations feel natural

---

## 🔧 Troubleshooting

### Backend won't start
```bash
# Check if port is in use
lsof -i :8000

# Kill process
kill -9 <PID>

# Restart
python backend/main.py
```

### Mobile app won't connect
1. Check `.env` file has correct API URL:
   ```
   API_BASE_URL=http://localhost:8000
   ```

2. If using physical device, use your local IP:
   ```bash
   # Find your IP
   ipconfig getifaddr en0  # macOS WiFi
   
   # Update .env
   API_BASE_URL=http://192.168.x.x:8000
   ```

3. Restart Expo after changing .env

### No insights appear
1. Verify backend is running
2. Check backend logs for errors
3. Verify test data was populated:
   ```bash
   sqlite3 insights.db "SELECT COUNT(*) FROM insights;"
   # Should show: 9
   ```

4. Re-run test data script:
   ```bash
   python tests/populate_test_data.py
   ```

### Engagement not persisting
- Check AsyncStorage is enabled
- Clear app data and restart
- Check backend logs for POST errors

---

## 📊 Database Queries for Debugging

```sql
-- Check insights
SELECT id, topic, category, text FROM insights LIMIT 5;

-- Check user topics
SELECT * FROM user_topics WHERE user_id = 'default';

-- Check engagement
SELECT insight_id, action, created_at FROM user_engagement 
WHERE user_id = 'default' 
ORDER BY created_at DESC 
LIMIT 10;

-- Check feed scores
SELECT topic, COUNT(*) as count, AVG(quality_score) as avg_quality 
FROM insights 
GROUP BY topic;
```

---

## 🚀 Next Steps After Testing

### If Tests Pass ✅
1. Add more test data (50+ insights)
2. Test with real production API
3. Build for TestFlight
4. Beta test with users

### Production Deployment
1. Run migration on production database
2. Deploy backend updates
3. Test production API
4. Deploy mobile app update

### Future Enhancements
- [ ] Topic management UI (follow/unfollow in-app)
- [ ] Saved insights screen
- [ ] Search functionality
- [ ] Share insights
- [ ] Notifications for new insights

---

## 📝 Test Results Log

Date: ___________  
Tester: ___________

### Following Feed
- [ ] Loads correctly
- [ ] Shows correct topics
- [ ] Infinite scroll works
- [ ] Engagement works
- Issues: ___________

### For You Feed
- [ ] Loads correctly
- [ ] Shows all topics
- [ ] Ranking makes sense
- [ ] Engagement works
- Issues: ___________

### Performance
- Load time: _____ seconds
- Scroll FPS: _____ fps
- Memory usage: _____ MB
- Issues: ___________

### Overall
Rating: ___ / 10
Ready for production: [ ] Yes [ ] No
Notes: ___________

---

**Last Updated:** Dec 2, 2025  
**Status:** Ready for testing 🚀
