# User and Admin Flows

## End User Flow

### 1) Register and login

- Register: `GET/POST /register/`
- Login: `GET/POST /login/`
- Logout: `POST /logout/`

### 2) Manage profile

- Open profile: `GET /profile/`
- Update profile fields/photo
- Change password from same profile page

### 3) Upload and parse resume

- Upload form: `GET/POST /resumes/upload/`
- Detail view: `GET /resumes/<id>/`
- JSON download: `GET /resumes/<id>/download/`

Expected behavior:

- File validated for extension (`.pdf`, `.docx`) and size (`RESUME_MAX_FILE_SIZE_MB`)
- Resume is parsed through AI service or local fallback

### 4) Browse jobs and run match

- Jobs list: `GET /jobs/`
- Job detail: `GET /jobs/<id>/`
- Match call: `POST /jobs/<id>/match/` with `resume_id`
- Match detail page: `GET /matches/<id>/`

### 5) Analyze skill gaps

- Skill-gap call: `POST /jobs/<id>/skill-gap/` with `resume_id`

### 6) Save/unsave jobs

- Toggle saved state: `POST /jobs/<id>/save/`
- Saved list page: `GET /saved-jobs/`

### 7) Get recommendations

- Recommendations page: `GET /recommendations/`
- Supports optional API job refresh with query/location/limit
- Stores results into `Recommendation` table

## Admin Flow

Requires `is_staff=true`.

### 1) Analytics

- Dashboard: `GET /admin/dashboard/`
- Shows resume count, saved jobs count, average score, top skills, top recommended jobs

### 2) Job management

- List: `GET /admin/jobs/`
- Create: `GET/POST /admin/jobs/new/`
- Edit: `GET/POST /admin/jobs/<id>/edit/`
- Delete: `POST /admin/jobs/<id>/delete/`

### 3) Django native admin

- `GET /admin/` for built-in Django admin site
