# 🚀 Hugging Face Spaces Deployment

## Quick Deploy (3 Steps)

### 1. Create Space
- Go to https://huggingface.co/spaces
- Click "Create new Space"
- Name: `carbon-aware-scheduler`
- SDK: **Docker**
- License: MIT
- Visibility: Public

### 2. Push Code
```bash
# Clone your Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/carbon-aware-scheduler
cd carbon-aware-scheduler

# Copy all project files
cp -r /path/to/carbon-scheduler/* .

# Commit and push
git add .
git commit -m "Deploy Carbon-Aware Scheduler"
git push
```

### 3. Wait for Build
- Build time: ~5-10 minutes
- Your Space will be live at: `https://huggingface.co/spaces/YOUR_USERNAME/carbon-aware-scheduler`

## ✅ Pre-Deployment Checklist

**Test locally first:**
```bash
# Test Streamlit
streamlit run app.py

# Test Docker
docker build -t carbon-scheduler .
docker run -p 7860:7860 carbon-scheduler

# Run validation
python test_submission.py
```

**All should pass:**
- [ ] UI loads and works
- [ ] All 3 tasks run successfully
- [ ] Charts display correctly
- [ ] No errors in console
- [ ] Tests pass (Phase 1, 2, 3)

## 🐛 Troubleshooting

**Build fails:** Check Dockerfile syntax, verify requirements.txt  
**Port issues:** Ensure EXPOSE 7860 and correct CMD in Dockerfile  
**Import errors:** Verify all `__init__.py` files exist  

## 📊 What Judges Will See

1. Interactive Streamlit dashboard
2. Task selection (Easy/Medium/Hard)
3. Optimizer comparison
4. Gantt charts with priority colors
5. Carbon intensity graphs
6. Explainable AI decisions
7. Real-time metrics

---

**Your deployment is ready!** The Dockerfile is pre-configured for Hugging Face Spaces.
