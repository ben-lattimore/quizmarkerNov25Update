# QuizMarker Migration Plan: Approach B - Modern SaaS

**Goal**: Transform QuizMarker from a Replit monolith into a production-ready SaaS application with Next.js frontend and Flask API backend.

**Timeline**: 6-10 weeks
**Target**: Professional B2B SaaS product ready to sell to customers

---

## Architecture Overview

### Current State (Replit)
```
Flask Monolith (app.py)
├── Server-rendered Jinja2 templates
├── Session-based authentication
├── Synchronous AI processing (blocks requests)
├── Temporary file storage (/tmp)
└── Single PostgreSQL database
```

### Target State (Production SaaS)
```
┌──────────────────────────────────────────────────────┐
│  Next.js Frontend (Vercel)                           │
│  - Modern React UI with TypeScript                   │
│  - Real-time progress tracking                       │
│  - Client-side state management                      │
└──────────────────────────────────────────────────────┘
                      ↓ REST API (JSON)
┌──────────────────────────────────────────────────────┐
│  Flask API Backend (Railway/Render)                  │
│  - JWT authentication                                │
│  - API-first design (/api/v1/*)                     │
│  - Background job processing (Celery/RQ + Redis)    │
│  - File storage (AWS S3)                            │
└──────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    PostgreSQL      Redis/Queue      AWS S3
```

---

## PHASE 1: Foundation & Environment Setup
**Duration**: Week 1
**Focus**: Prepare local development environment and infrastructure

### Tasks

#### 1.1 Local Development Environment
- [ ] Install and configure local PostgreSQL database
- [ ] Create `.env.example` and `.env` files with all required variables
- [ ] Remove Replit-specific dependencies:
  - Replace `cdn.replit.com` Bootstrap with standard CDN or Tailwind
  - Remove `.replit` and `replit.nix` files (keep for reference)
- [ ] Test application runs locally with PostgreSQL
- [ ] Document any issues encountered

**Environment Variables Needed**:
```
DATABASE_URL=postgresql://localhost/quizmarker_dev
OPENAI_API_KEY=sk-...
SENDGRID_API_KEY=SG...
SESSION_SECRET=random-secret-key
FLASK_ENV=development
```

#### 1.2 Version Control & Branching Strategy
- [ ] Create `development` branch from `main`
- [ ] Create `.gitignore` additions:
  - `.env` and `.env.local`
  - `*.db` (SQLite files)
  - `__pycache__/`
  - `node_modules/` (for future frontend)
  - `.next/` (for future frontend)
- [ ] Set up branch protection rules (if using GitHub)
- [ ] Document git workflow in README

**Git Workflow**:
```
main (production) ← staging ← development ← feature branches
```

#### 1.3 Infrastructure Accounts Setup
- [ ] **Railway** or **Render**: Backend hosting
  - Sign up for account
  - Verify credit card for production usage
  - Note: Start with free tier, upgrade when deploying

- [ ] **Vercel**: Frontend hosting
  - Sign up with GitHub account
  - Free tier is sufficient to start

- [ ] **AWS**: S3 file storage
  - Create AWS account
  - Set up IAM user with S3 access only
  - Create S3 bucket (e.g., `quizmarker-uploads-prod`)
  - Note access key and secret

- [ ] **Sentry**: Error monitoring
  - Sign up for free tier
  - Create new project for "quizmarker-backend"
  - Create new project for "quizmarker-frontend"
  - Note DSN keys

#### 1.4 Documentation
- [ ] Document all current API endpoints:
  - Method, path, inputs, outputs, authentication required
  - Use a spreadsheet or markdown table

- [ ] Document database schema:
  - All tables, relationships, constraints
  - Can use a tool like dbdiagram.io

- [ ] Create environment variables documentation:
  - What each variable does
  - Where to get values
  - Required vs optional

**Deliverable**:
✅ Clean local development environment
✅ All infrastructure accounts created
✅ Comprehensive documentation of current system

---

## PHASE 2: Backend API Conversion
**Duration**: Weeks 2-3
**Focus**: Transform Flask from monolith to API-first backend

### Tasks

#### 2.1 Refactor Flask App to API-First
- [ ] Create Flask Blueprint structure:
  ```
  /api
    /v1
      /auth (login, register, reset password)
      /quizzes (list, view, delete)
      /upload (file upload)
      /grade (grading endpoint)
      /standards (available standards)
  ```
- [ ] Move existing route logic to API blueprint
- [ ] Convert all endpoints to return JSON (remove `render_template`)
- [ ] Keep old routes temporarily for comparison
- [ ] Add API versioning (`/api/v1/`)

**Example Endpoint Transformation**:
```
OLD: GET /quizzes → Returns HTML
NEW: GET /api/v1/quizzes → Returns JSON list
```

#### 2.2 Authentication Overhaul
- [ ] Install JWT library (`PyJWT` or `flask-jwt-extended`)
- [ ] Implement token generation on login
- [ ] Implement token refresh endpoint
- [ ] Add JWT verification decorator for protected routes
- [ ] Update password reset to work with API (email link → frontend)
- [ ] Add CORS configuration (flask-cors)
- [ ] Test authentication flow with Postman/Insomnia

**Auth Flow**:
```
POST /api/v1/auth/login → Returns {access_token, refresh_token}
GET /api/v1/quizzes (Header: Authorization: Bearer <token>)
POST /api/v1/auth/refresh → Returns new access_token
```

#### 2.3 File Upload Improvements
- [ ] Install boto3 (AWS SDK for Python)
- [ ] Create S3 service wrapper (upload, delete, generate presigned URLs)
- [ ] Update upload endpoint to:
  - Save file to S3 (not /tmp)
  - Store S3 key in database
  - Return S3 URL in response
- [ ] Implement file cleanup job (delete old files after X days)
- [ ] Add file size and type validation
- [ ] Test S3 integration thoroughly

**S3 Integration Pattern**:
```
1. Frontend uploads file to /api/v1/upload
2. Backend saves to S3: s3://bucket/uploads/{user_id}/{uuid}/{filename}
3. Store S3 key in QuizSubmission.uploaded_files (new JSON column)
4. Return S3 URL to frontend
```

#### 2.4 API Structure & Validation
- [ ] Choose validation library (Marshmallow or Pydantic)
- [ ] Create schemas for all request/response bodies
- [ ] Standardize API response format:
  ```json
  Success: {"success": true, "data": {...}}
  Error: {"success": false, "error": "message", "code": "ERROR_CODE"}
  ```
- [ ] Add proper HTTP status codes (200, 201, 400, 401, 404, 500)
- [ ] Install and configure rate limiting (flask-limiter)
- [ ] Set rate limits per endpoint (e.g., 10 uploads/hour per user)

#### 2.5 Database Enhancements
- [ ] Install and configure Alembic (database migrations)
- [ ] Create initial migration from current schema
- [ ] Add new models:
  - `Organization` (for multi-tenancy)
  - `OrganizationMember` (users in organizations)
  - `APIUsageLog` (track API calls for billing)
- [ ] Update existing models:
  - Add `organization_id` to relevant tables
  - Add `uploaded_files` JSON column to QuizSubmission
  - Add indexes for performance
- [ ] Create migration for changes
- [ ] Test migration up and down

**New Schema**:
```
Organization
  ├── id, name, created_at
  └── plan (free, pro, enterprise)

OrganizationMember
  ├── organization_id
  ├── user_id
  └── role (owner, admin, member)

User (updated)
  └── default_organization_id
```

**Deliverable**:
✅ Flask API backend that returns JSON
✅ JWT authentication working
✅ Files stored in S3
✅ Database ready for multi-tenancy
✅ API documented and tested

---

## PHASE 3: Async Processing & Background Jobs
**Duration**: Week 4
**Focus**: Make AI processing non-blocking

### Tasks

#### 3.1 Job Queue Setup
- [ ] **Choose queue system**:
  - **Celery + Redis**: More powerful, better for scale
  - **RQ (Redis Queue)**: Simpler, easier to learn
  - **Recommendation**: Start with RQ, migrate to Celery if needed

- [ ] Install Redis locally (Mac: `brew install redis`)
- [ ] Install queue library (`pip install rq` or `pip install celery`)
- [ ] Create worker configuration
- [ ] Create tasks module (`tasks.py` or `/tasks/`)
- [ ] Test basic job execution locally

**Redis Setup**:
```bash
# Local
redis-server

# Railway/Render
Add Redis addon in dashboard
```

#### 3.2 Convert Sync to Async
- [ ] Move image processing to background task:
  ```
  OLD: /upload → Process images → Return results (60s)
  NEW: /upload → Queue job → Return job_id (instant)
  ```
- [ ] Move grading to background task
- [ ] Create job status endpoint: `GET /api/v1/jobs/{job_id}`
- [ ] Add job result storage (Redis or database)
- [ ] Implement polling mechanism (frontend checks job status)
- [ ] Optional: Add WebSocket for real-time updates

**Job Flow**:
```
1. POST /api/v1/upload → {job_id: "abc123", status: "queued"}
2. Worker picks up job → processes images
3. GET /api/v1/jobs/abc123 → {status: "processing", progress: 50%}
4. Job completes → {status: "completed", data: {...}}
```

#### 3.3 Job Monitoring
- [ ] Add job retry logic (retry on failure, max 3 attempts)
- [ ] Add job timeout (kill after 5 minutes)
- [ ] Add job failure handling (store error message)
- [ ] Create job cleanup task (delete old jobs after 24 hours)
- [ ] Add logging for job lifecycle
- [ ] Test failure scenarios (API timeout, invalid file, etc.)

**Deliverable**:
✅ Non-blocking API that handles long-running operations
✅ Job status polling working
✅ Retry and error handling implemented
✅ Ready for frontend integration

---

## PHASE 4: Frontend Development - Next.js
**Duration**: Weeks 5-7
**Focus**: Build modern React frontend

### Tasks

#### 4.1 Next.js Project Setup
- [ ] Create new Next.js project:
  ```bash
  npx create-next-app@latest quizmarker-frontend
  # Choose: TypeScript, Tailwind CSS, App Router, no src/
  ```
- [ ] Install dependencies:
  - UI library: `npx shadcn-ui@latest init` (recommended)
  - Or: Material-UI, Chakra UI
  - HTTP client: `axios` or `@tanstack/react-query`
  - Form library: `react-hook-form`
  - Date handling: `date-fns`
- [ ] Configure environment variables (`.env.local`)
- [ ] Set up folder structure:
  ```
  /app (pages)
  /components (reusable components)
  /lib (utilities, API client)
  /hooks (custom React hooks)
  /types (TypeScript types)
  ```

#### 4.2 Authentication UI
- [ ] Create auth context/provider for global auth state
- [ ] Build `/login` page
- [ ] Build `/register` page
- [ ] Build `/forgot-password` page
- [ ] Build `/reset-password` page
- [ ] Implement token storage (httpOnly cookies recommended)
- [ ] Create protected route wrapper component
- [ ] Add auto-redirect if not authenticated
- [ ] Add auto-logout on token expiration

**Auth Flow**:
```
1. User logs in → Store JWT in httpOnly cookie
2. All API calls include cookie automatically
3. Backend verifies JWT on each request
4. Token expires → Auto redirect to login
```

#### 4.3 Core Feature Pages
- [ ] **Dashboard/Home** (`/app/page.tsx`):
  - File upload zone (drag-drop)
  - Standard selector dropdown
  - Student name input
  - Quiz title input
  - Upload button

- [ ] **Upload Component**:
  - Drag and drop file upload
  - File preview (thumbnails)
  - File removal before upload
  - Progress bar during upload
  - Multiple file support

- [ ] **Job Progress Component**:
  - Poll job status every 2 seconds
  - Show progress bar
  - Show current step (extracting, grading, saving)
  - Show results when complete

- [ ] **Results Display** (`/app/results/[id]/page.tsx`):
  - Show quiz summary
  - Show each question with score
  - Show AI feedback
  - Show handwritten content extracted
  - Download/export option

- [ ] **Quiz List** (`/app/quizzes/page.tsx`):
  - Table of all submissions
  - Filters (student, date range, standard)
  - Pagination
  - Click to view detail

- [ ] **Quiz Detail** (`/app/quizzes/[id]/page.tsx`):
  - Full submission detail
  - All questions and answers
  - Edit/delete options (if owner/admin)

#### 4.4 Admin Features
- [ ] **Admin Dashboard** (`/app/admin/page.tsx`):
  - Organization stats
  - Recent activity
  - User list

- [ ] **User Management** (`/app/admin/users/page.tsx`):
  - List all users
  - Add/remove users
  - Change roles

- [ ] **Settings** (`/app/settings/page.tsx`):
  - Profile settings
  - Organization settings
  - API keys (if exposing API)

#### 4.5 State Management & API Client
- [ ] Create API client wrapper:
  - Base URL from environment variable
  - Auto-attach JWT token
  - Handle 401 (redirect to login)
  - Handle errors globally

- [ ] Set up React Query (recommended for server state):
  - Cache API responses
  - Auto-refetch on window focus
  - Optimistic updates

- [ ] Create custom hooks:
  - `useAuth()` - Auth state and methods
  - `useQuizzes()` - Fetch quiz list
  - `useUpload()` - Handle file upload
  - `useJobStatus()` - Poll job status

- [ ] Add loading states (skeletons, spinners)
- [ ] Add error handling (toast notifications)
- [ ] Add success feedback (toast, confetti)

**API Client Example**:
```typescript
// lib/api.ts
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true // Include cookies
});

// Auto-redirect on 401
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

**Deliverable**:
✅ Complete Next.js frontend with all pages
✅ Authentication flow working
✅ File upload with progress tracking
✅ Quiz viewing and management
✅ Admin panel functional

---

## PHASE 5: Integration & Testing
**Duration**: Week 8
**Focus**: Connect frontend to backend and test thoroughly

### Tasks

#### 5.1 Frontend-Backend Integration
- [ ] Run both apps locally (Flask on :5000, Next.js on :3000)
- [ ] Configure CORS to allow localhost:3000
- [ ] Test authentication flow:
  - Registration
  - Login
  - Logout
  - Password reset
- [ ] Test file upload → job creation → polling → results
- [ ] Test quiz list and detail views
- [ ] Test all CRUD operations (create, read, update, delete)
- [ ] Fix any integration issues

#### 5.2 Error Handling & Edge Cases
- [ ] Add error boundaries in Next.js (catch component errors)
- [ ] Test API errors display correctly (toast/alert)
- [ ] Test network failure scenarios:
  - API down
  - Slow connection
  - Request timeout
- [ ] Test job failures:
  - OpenAI API timeout
  - Invalid file format
  - File too large
- [ ] Add user-friendly error messages
- [ ] Test form validation (all required fields)

#### 5.3 Performance Optimization
- [ ] Add loading skeletons for async content
- [ ] Implement pagination for quiz list (20 per page)
- [ ] Add client-side caching (React Query)
- [ ] Optimize images (Next.js Image component)
- [ ] Test upload with large files (10MB+)
- [ ] Add image compression before upload (optional)
- [ ] Test with slow 3G network (Chrome DevTools)

#### 5.4 Testing
- [ ] **Manual Testing Checklist**:
  - [ ] Register new user
  - [ ] Login with correct/incorrect credentials
  - [ ] Upload single image
  - [ ] Upload multiple images (5+)
  - [ ] Test each standard (Standard 1-19)
  - [ ] View quiz list
  - [ ] View quiz detail
  - [ ] Delete quiz
  - [ ] Admin: view all quizzes
  - [ ] Admin: manage users
  - [ ] Forgot password flow
  - [ ] Reset password flow

- [ ] **Cross-browser Testing**:
  - [ ] Chrome
  - [ ] Firefox
  - [ ] Safari
  - [ ] Edge

- [ ] **Mobile Testing**:
  - [ ] iPhone Safari
  - [ ] Android Chrome
  - [ ] Responsive design on all pages

**Deliverable**:
✅ Fully integrated application working locally
✅ All features tested and working
✅ Edge cases handled gracefully
✅ Cross-browser and mobile compatible

---

## PHASE 6: Production Deployment
**Duration**: Week 9
**Focus**: Deploy to production infrastructure

### Tasks

#### 6.1 Backend Deployment to Railway/Render

**Railway** (Recommended):
- [ ] Connect GitHub repository
- [ ] Add service: "Deploy from GitHub repo"
- [ ] Configure build:
  - Build command: (auto-detected)
  - Start command: `gunicorn main:app`
- [ ] Add PostgreSQL database addon
- [ ] Add Redis addon
- [ ] Set environment variables:
  ```
  DATABASE_URL=(auto-populated from addon)
  REDIS_URL=(auto-populated from addon)
  OPENAI_API_KEY=sk-...
  SENDGRID_API_KEY=SG...
  SESSION_SECRET=random-production-secret
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  S3_BUCKET_NAME=quizmarker-uploads-prod
  FLASK_ENV=production
  SENTRY_DSN=https://...
  ```
- [ ] Deploy and test
- [ ] Run database migrations (connect via Railway CLI)
- [ ] Create first admin user
- [ ] Test all API endpoints in production
- [ ] Note production API URL

**Or Render**:
- [ ] Create new Web Service
- [ ] Connect GitHub repository
- [ ] Configure:
  - Build command: `pip install -r requirements.txt`
  - Start command: `gunicorn main:app`
- [ ] Add PostgreSQL database
- [ ] Add Redis instance
- [ ] Set environment variables (same as above)
- [ ] Deploy

**Start Worker Process**:
- [ ] Create separate service for background worker
- [ ] Start command: `rq worker` or `celery worker`
- [ ] Should share same Redis and Database

#### 6.2 Frontend Deployment to Vercel
- [ ] Push frontend to GitHub repository
- [ ] Go to Vercel dashboard
- [ ] Import project from GitHub
- [ ] Configure:
  - Framework Preset: Next.js (auto-detected)
  - Root Directory: `./` or `./frontend` if in subdirectory
- [ ] Set environment variables:
  ```
  NEXT_PUBLIC_API_URL=https://your-backend.railway.app
  ```
- [ ] Deploy
- [ ] Test production build
- [ ] Configure custom domain (optional):
  - Add domain in Vercel settings
  - Update DNS records as instructed
  - SSL auto-configured by Vercel

#### 6.3 Services Configuration
- [ ] **S3 Bucket**:
  - Set bucket policy for public read (or presigned URLs)
  - Configure CORS to allow uploads from your domains
  - Test upload from production frontend

- [ ] **Redis**:
  - Verify connection from worker
  - Test job creation and processing

- [ ] **SendGrid**:
  - Verify sender email (hello@benlattimore.com)
  - Add domain authentication (optional but recommended)
  - Test welcome email
  - Test password reset email
  - Test quiz completion email

- [ ] **Sentry**:
  - Verify errors are being captured
  - Test by triggering an error
  - Set up alerts (email on new errors)
  - Configure ignored errors (known issues)

#### 6.4 Monitoring & Logging
- [ ] **Sentry Setup**:
  - Backend: Install sentry-sdk
  - Frontend: Install @sentry/nextjs
  - Test error tracking in both

- [ ] **Logging**:
  - Configure Railway/Render log retention
  - Set up log aggregation (optional: Logtail, Papertrail)
  - Add structured logging to critical paths

- [ ] **Uptime Monitoring**:
  - Sign up for UptimeRobot or similar (free tier)
  - Monitor frontend and backend URLs
  - Set up alerts (email/SMS on downtime)

- [ ] **Performance Monitoring**:
  - Use Vercel Analytics (free with Vercel)
  - Monitor API response times in Railway/Render dashboard
  - Set up alerts for slow endpoints

**Deliverable**:
✅ Application live in production
✅ Frontend and backend deployed and connected
✅ All services configured and tested
✅ Monitoring and alerting active
✅ Production URL shared with stakeholders

---

## PHASE 7: Post-Launch Essentials
**Duration**: Week 10+
**Focus**: Polish, security, and customer readiness

### Tasks

#### 7.1 Security Hardening
- [ ] **Security Audit**:
  - Review all API endpoints for authorization (can user access this resource?)
  - Review file upload validation (file type, size, content)
  - Check for SQL injection risks (should be safe with SQLAlchemy)
  - Check for XSS risks (should be safe with React)
  - Test CSRF protection on API endpoints

- [ ] **Rate Limiting**:
  - Add per-user rate limits (100 requests/hour)
  - Add per-organization limits (500 requests/hour)
  - Add stricter limits on expensive endpoints (/upload: 10/hour)

- [ ] **Security Headers**:
  - Add to Flask app:
    - `X-Frame-Options: DENY`
    - `X-Content-Type-Options: nosniff`
    - `Strict-Transport-Security: max-age=31536000`
  - Vercel adds most headers automatically

- [ ] **HTTPS Enforcement**:
  - Ensure all URLs use https://
  - Redirect http:// to https:// (Railway/Vercel do this)
  - Update CORS to only allow https origins

- [ ] **Monitor Sentry**:
  - Review errors from first week
  - Fix critical bugs
  - Add handling for common errors

#### 7.2 Documentation
- [ ] **API Documentation**:
  - Use Swagger/OpenAPI (flask-swagger-ui)
  - Or create simple markdown docs
  - Document all endpoints, request/response formats
  - Add authentication instructions
  - Host at `/api/v1/docs`

- [ ] **User Guide**:
  - How to sign up
  - How to upload and grade quizzes
  - How to view results
  - Troubleshooting common issues

- [ ] **Admin Guide**:
  - How to manage users
  - How to clean database
  - How to view logs
  - How to handle support requests

- [ ] **Deployment Runbook**:
  - How to deploy backend
  - How to deploy frontend
  - How to run migrations
  - How to roll back
  - Emergency procedures

#### 7.3 Billing Integration (If needed immediately)
- [ ] **Stripe Setup**:
  - Sign up for Stripe account
  - Install stripe Python library
  - Create products and prices:
    - Free tier: 10 quizzes/month
    - Pro tier: $29/month, 100 quizzes/month
    - Enterprise tier: $99/month, unlimited

- [ ] **Subscription Flow**:
  - Add checkout page (Stripe Checkout)
  - Add webhook endpoint for subscription updates
  - Add subscription status to Organization model
  - Enforce limits based on plan

- [ ] **Usage Tracking**:
  - Track quizzes graded per organization
  - Show usage in dashboard
  - Send email at 80% of limit
  - Block at 100% (or allow overage)

- [ ] **Billing Dashboard**:
  - Show current plan
  - Show usage this month
  - Upgrade/downgrade buttons
  - Invoice history

#### 7.4 Customer Features
- [ ] **Onboarding Flow**:
  - Welcome modal on first login
  - Guided tour of features
  - Sample quiz to try
  - Link to documentation

- [ ] **Email Notifications**:
  - Job completed: "Your quiz has been graded"
  - Weekly summary: "You graded X quizzes this week"
  - Billing: "Payment successful", "Payment failed"

- [ ] **Error Messages**:
  - Review all error messages for clarity
  - Make user-friendly (not technical)
  - Add suggestions for fixes

- [ ] **Feedback Mechanism**:
  - Add feedback button in app
  - Collect feedback via form or email
  - Or integrate Intercom/Crisp for live chat

**Deliverable**:
✅ Secure, production-ready application
✅ Comprehensive documentation
✅ Billing system working (if needed)
✅ Ready to onboard paying customers
✅ Support system in place

---

## Key Decisions to Make Early

### 1. UI Library
- **shadcn/ui** (Recommended): Modern, customizable, Tailwind-based
- **Material-UI**: More complete, corporate look
- **Chakra UI**: Good middle ground
- **Decision needed by**: Week 5 (before frontend development)

### 2. Queue System
- **RQ (Redis Queue)**: Simpler, good for starting, Python-native
- **Celery**: More powerful, better for scale, more complex
- **Decision needed by**: Week 4 (before async implementation)

### 3. Hosting Provider
- **Railway**: Easier setup, better DX, slightly more expensive
- **Render**: Cheaper, more established, slightly more complex
- **Decision needed by**: Week 1 (account setup)

### 4. CSS Framework
- **Tailwind CSS**: Modern, utility-first, recommended with Next.js
- **Bootstrap**: Familiar, component-based, what you have now
- **Decision needed by**: Week 5 (frontend setup)

### 5. State Management
- **React Query**: Best for server state, recommended
- **Zustand**: Good for client state
- **Context API**: Built-in, simple, good to start
- **Decision needed by**: Week 5 (frontend setup)

---

## Risks & Mitigation Strategies

### Risk 1: Learning Curve for Next.js
**Impact**: High - Could delay frontend development
**Likelihood**: Medium
**Mitigation**:
- Complete Next.js tutorial before starting (1-2 days)
- Start with simple pages, add complexity incrementally
- Use ChatGPT/Claude for code examples
- Leverage shadcn/ui for pre-built components

### Risk 2: Async Job Complexity
**Impact**: High - Core feature could be buggy
**Likelihood**: Medium
**Mitigation**:
- Start with simplest queue system (RQ)
- Test thoroughly with small examples first
- Add comprehensive logging
- Keep synchronous option as fallback initially

### Risk 3: AWS/S3 Complexity
**Impact**: Medium - File storage could fail
**Likelihood**: Medium
**Mitigation**:
- Use Railway's file storage temporarily
- Migrate to S3 after core features work
- Or use managed service (Uploadcare, Cloudinary)
- Test uploads extensively in staging

### Risk 4: Migration Breaking Functionality
**Impact**: High - Could lose working features
**Likelihood**: Low (if careful)
**Mitigation**:
- Keep old Flask app running in parallel
- Test each migration step thoroughly
- Have rollback plan for each phase
- Don't delete old code until new version is stable

### Risk 5: OpenAI API Costs
**Impact**: High - Could be expensive at scale
**Likelihood**: High (if successful)
**Mitigation**:
- Implement strict rate limiting
- Add usage alerts (email at $100/day)
- Cache results where possible
- Consider offering "fast" vs "economy" grading

### Risk 6: Multi-tenancy Bugs
**Impact**: Critical - Could leak data between customers
**Likelihood**: Medium
**Mitigation**:
- Add organization_id to ALL queries
- Use Row Level Security in PostgreSQL (advanced)
- Extensive testing with multiple test organizations
- Security audit before launch

---

## Success Criteria

### Phase 1 Success
- [ ] Local environment running smoothly
- [ ] All infrastructure accounts created
- [ ] Documentation complete and clear

### Phase 2 Success
- [ ] All API endpoints return JSON
- [ ] JWT authentication works in Postman
- [ ] Files stored in S3 successfully
- [ ] Database migrations working

### Phase 3 Success
- [ ] Long-running jobs don't block API
- [ ] Job status polling works reliably
- [ ] Retry logic handles failures gracefully

### Phase 4 Success
- [ ] Frontend looks professional
- [ ] All pages render correctly
- [ ] Forms work and validate properly
- [ ] Authentication flow smooth

### Phase 5 Success
- [ ] Frontend and backend communicate perfectly
- [ ] No critical bugs in main user flows
- [ ] Error handling provides good UX
- [ ] Performance is acceptable (< 2s page loads)

### Phase 6 Success
- [ ] Application accessible at production URLs
- [ ] No deployment errors
- [ ] Monitoring shows healthy status
- [ ] First test user can complete full flow

### Phase 7 Success
- [ ] No security vulnerabilities found
- [ ] Documentation complete and helpful
- [ ] Billing working (if implemented)
- [ ] Ready to share with real customers

---

## Final Launch Checklist

Before announcing to customers:

- [ ] All phases completed
- [ ] No critical bugs in Sentry
- [ ] Performance is good (Lighthouse score > 80)
- [ ] Mobile experience is smooth
- [ ] Documentation is complete
- [ ] Support email is set up
- [ ] Billing is working (if paid product)
- [ ] Terms of Service and Privacy Policy added
- [ ] GDPR compliance reviewed (if serving EU)
- [ ] Backup and disaster recovery plan documented
- [ ] Monitoring and alerts are working
- [ ] First 3 beta customers tested successfully

---

## Cost Estimate

### Development Phase (Weeks 1-10)
- Railway/Render (development): $20-30/month
- Vercel: Free
- AWS S3: $1-5/month
- Sentry: Free tier
- OpenAI API: $50-100/month (testing)
- **Total**: ~$100-150/month

### Production (Month 1-3, low usage)
- Railway/Render: $50/month
- Vercel: Free → $20/month
- AWS S3: $10/month
- Redis: Included in Railway, or $10/month
- PostgreSQL: Included in Railway, or $25/month
- Sentry: Free → $26/month
- OpenAI API: Variable ($100-500/month)
- **Total**: ~$200-700/month

### Production (Scaled, 100+ customers)
- Railway/Render: $200-500/month
- Vercel: $20/month
- AWS S3: $50/month
- Redis: $25/month
- PostgreSQL: $100/month
- Sentry: $80/month
- OpenAI API: $2,000-10,000/month (pass to customers)
- **Total**: ~$500/month + OpenAI costs

---

## Next Steps

1. Review this plan and confirm approach
2. Make key decisions (UI library, queue system, hosting)
3. Set up Phase 1 tasks in project management tool
4. Begin Phase 1 execution
5. Schedule weekly check-ins to review progress
6. Update this document as you learn and adapt

Good luck with the migration! 🚀
