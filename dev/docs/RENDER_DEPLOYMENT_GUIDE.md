# Render Deployment Guide - Ollama Cloud API

**Date:** 2026-01-05  
**Status:** Ready for Deployment

---

## Prerequisites

✅ Ollama Cloud API integration complete  
✅ API key configured  
✅ All code tested and working  
✅ No local dependencies

---

## Step 1: Prepare Repository

### 1.1 Commit All Changes
```bash
cd /home/clay/Desktop/SparksBM
git add .
git commit -m "Integrate Ollama Cloud API - Replace Gemini and local Ollama"
git push origin main
```

### 1.2 Verify Repository
- All files committed
- `.env` file should NOT be committed (contains API key)
- `requirements.txt` up to date

---

## Step 2: Create Render Services

### 2.1 NotebookLLM API Service

**Service Type:** Web Service

**Configuration:**
- **Name:** `sparksbm-api`
- **Runtime:** Python 3
- **Region:** Oregon (or closest to users)
- **Branch:** `main`
- **Root Directory:** `NotebookLLM/api`
- **Build Command:** 
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

**Environment Variables:**
```bash
# Ollama Cloud API
OLLAMA_API_KEY=6896f474b1284609b41725fbd69ae6cc.R1IYz7bOorDqm5WNguZLu6CJ
OLLAMA_ENDPOINT=https://ollama.com
OLLAMA_MODEL=ministral-3:8b

# Keycloak (if needed)
KEYCLOAK_URL=https://your-keycloak.render.com
KEYCLOAK_REALM=sparksbm
KEYCLOAK_CLIENT_ID=your-client-id
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Verinice Backend
VERINICE_API_URL=https://your-verinice.render.com
SPARKSBM_SCRIPTS_PATH=/opt/render/project/src

# Other
PYTHON_VERSION=3.11
```

**Plan:** Starter ($7/month) or Standard ($25/month)

---

### 2.2 Frontend Service (Optional)

**Service Type:** Static Site

**Configuration:**
- **Name:** `sparksbm-frontend`
- **Build Command:**
  ```bash
  cd SparksbmISMS/verinice-veo-web
  npm install
  npm run build
  ```
- **Publish Directory:** `SparksbmISMS/verinice-veo-web/.output/public`

**Plan:** Free

---

### 2.3 PostgreSQL Database (If Needed)

**Service Type:** PostgreSQL

**Configuration:**
- **Name:** `sparksbm-db`
- **Version:** 16
- **Plan:** Basic ($7/month)

**Connection:**
- Auto-generated `DATABASE_URL` environment variable
- Add to API service environment variables

---

## Step 3: Configure Environment Variables

### 3.1 In Render Dashboard

1. Go to your service
2. Click "Environment" tab
3. Add all required variables (see Step 2.1)
4. **Important:** Set `OLLAMA_API_KEY` securely
5. Save changes

### 3.2 Verify Variables

After deployment, check logs:
```bash
# In Render dashboard, check logs for:
✅ OLLAMA_API_KEY configured
✅ ReasoningEngine initialized
```

---

## Step 4: Deploy

### 4.1 Initial Deployment

1. **Connect Repository:**
   - Go to Render Dashboard
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Select branch: `main`

2. **Configure Service:**
   - Use settings from Step 2.1
   - Add environment variables
   - Click "Create Web Service"

3. **Monitor Deployment:**
   - Watch build logs
   - Check for errors
   - Wait for "Live" status

### 4.2 Post-Deployment Testing

**Test 1: Health Check**
```bash
curl https://your-service.onrender.com/health
```

**Test 2: Knowledge Question**
```bash
curl -X POST https://your-service.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is ISO 27001?",
    "sessionId": "test-session"
  }'
```

**Test 3: Document Upload**
```bash
curl -X POST https://your-service.onrender.com/api/upload \
  -F "file=@test.xlsx" \
  -F "sessionId=test-session"
```

---

## Step 5: Monitor Usage

### 5.1 Rate Limit Monitoring

**Set Up Alerts:**
1. Monitor API response times
2. Watch for HTTP 429 errors
3. Track daily API call count

**Monitoring Script:**
```bash
# Run locally to monitor usage
python3 dev/test/monitorOllamaUsage.py --stats
```

### 5.2 Usage Tracking

**Check Logs:**
- Render dashboard → Logs
- Look for "Ollama API" entries
- Monitor response times
- Watch for errors

**Daily Checks:**
- Total API calls
- Success rate
- Average response time
- Rate limit errors

---

## Step 6: Cost Management

### 6.1 Current Costs (Free Tier)

- **Ollama Cloud:** $0/month
- **Render Web Service:** $7/month (Starter)
- **Render PostgreSQL:** $7/month (Basic)
- **Total:** ~$14/month

### 6.2 If Rate Limits Hit

**Upgrade to Pro:**
- **Ollama Cloud Pro:** $20/month
- **Total:** ~$34/month

**Optimization:**
- Cache frequent queries
- Batch requests when possible
- Monitor and optimize usage

---

## Troubleshooting

### Issue: API Not Responding

**Check:**
1. Environment variables set correctly
2. API key valid
3. Service is "Live" (not "Building")
4. Check logs for errors

**Solution:**
```bash
# Check logs in Render dashboard
# Look for:
- "OLLAMA_API_KEY not found" → Add env var
- "Connection refused" → Check endpoint
- "Model not found" → Check OLLAMA_MODEL
```

### Issue: Rate Limit Errors

**Symptoms:**
- HTTP 429 errors
- "rate limit exceeded" messages
- Slow responses

**Solution:**
1. Wait and retry
2. Upgrade to Pro tier
3. Implement request throttling
4. Cache responses

### Issue: Slow Responses

**Check:**
- API response times in logs
- Network latency
- Model size (try smaller model)

**Solution:**
- Use faster model (e.g., `ministral-3:3b`)
- Implement caching
- Optimize queries

---

## Rollback Plan

### If Issues Occur

1. **Revert Code:**
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Or Switch to Fallback:**
   - Set `OLLAMA_API_KEY=""` (empty)
   - System will use FallbackReasoningEngine
   - Pattern-based responses only

3. **Or Use Gemini (Old):**
   - Restore `LLMTool` usage
   - Set `GEMINI_API_KEY`
   - Revert ReasoningEngine changes

---

## Success Criteria

✅ API service deployed and running  
✅ Knowledge questions working  
✅ Document analysis working  
✅ No rate limit errors  
✅ Response times < 5 seconds  
✅ Cost within budget  

---

## Next Steps After Deployment

1. **Monitor for 1 week:**
   - Track usage
   - Watch for errors
   - Monitor costs

2. **Optimize:**
   - Cache frequent queries
   - Optimize model selection
   - Fine-tune timeouts

3. **Scale if needed:**
   - Upgrade Ollama tier
   - Upgrade Render plan
   - Add caching layer

---

**Status:** ✅ Ready for Deployment  
**Last Updated:** 2026-01-05  
**Next Review:** After first week of production
