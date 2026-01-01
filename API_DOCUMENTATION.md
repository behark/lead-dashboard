# 📡 Dashboard API Documentation

## Saved Filters API

### POST /save-filter
Save a filter combination for reuse

**Parameters:**
```json
{
  "filter_name": "Hot Leads This Week",
  "filter_desc": "New hot leads from this week",
  "is_favorite": true,
  "filters": {
    "search": "",
    "status": "NEW",
    "temp": "HOT",
    "country": "Kosovo",
    "category": "Restaurant",
    "assigned": "mine",
    "sort": "score"
  }
}
```

**Response:**
```json
{
  "success": true,
  "id": 42
}
```

---

### GET /load-filter/<filter_id>
Load a saved filter and redirect to dashboard with those filters applied

**Response:**
- Redirects to `/` with filter parameters in URL
- Updates `last_used` and `usage_count`

---

### POST /delete-filter/<filter_id>
Delete a saved filter

**Response:**
```json
{
  "success": true
}
```

---

## Bulk Operations API

### GET /bulk-jobs
Display bulk operations dashboard

**Response:**
- Renders HTML template with active and recent jobs
- Shows progress bars, stats, cancel buttons

---

### GET /bulk-job/<job_id>/status
Get real-time status of a bulk job

**Response:**
```json
{
  "id": 1,
  "status": "running",
  "processed": 45,
  "total": 100,
  "successful": 44,
  "failed": 1,
  "skipped": 0,
  "progress_percent": 45,
  "results": {
    "errors": [
      "Lead #123: Invalid phone number"
    ]
  }
}
```

---

### POST /bulk-job/<job_id>/cancel
Cancel a running bulk operation

**Response:**
```json
{
  "success": true,
  "message": "Job cancelled"
}
```

**Status codes:**
- `200` - Successfully cancelled
- `403` - Unauthorized
- `400` - Job is not active

---

## Lead Data API

### GET /api/leads
Get all leads for current user as JSON (for Kanban board)

**Response:**
```json
[
  {
    "id": 1,
    "name": "John's Restaurant",
    "phone": "+38345123456",
    "status": "NEW",
    "temperature": "HOT",
    "lead_score": 85,
    "category": "Restaurant",
    "city": "Prishtina"
  },
  ...
]
```

---

### POST /api/lead/<lead_id>/status
Update a single lead's status (for Kanban board drag-drop)

**Parameters:**
```json
{
  "status": "CONTACTED"
}
```

**Response:**
```json
{
  "success": true
}
```

**Valid statuses:**
- `NEW`
- `CONTACTED`
- `REPLIED`
- `CLOSED`
- `LOST`

---

## Data Models

### SavedFilter Model
```python
class SavedFilter(db.Model):
    id: Integer (primary key)
    user_id: Integer (foreign key → User)
    name: String(100) - Display name
    description: Text - Optional description
    filters: JSON - Filter parameters dict
    sort_by: String(20) - Sort method (default: 'score')
    created_at: DateTime - When created
    last_used: DateTime - Last time loaded
    usage_count: Integer - How many times used
    is_favorite: Boolean - Mark as favorite
```

**Filters dict structure:**
```python
{
    "search": "",
    "country": "",
    "category": "",
    "status": "",
    "temp": "",
    "assigned": "",
    "sort": "score"
}
```

---

### BulkJob Model
```python
class BulkJob(db.Model):
    id: Integer (primary key)
    user_id: Integer (foreign key → User)
    job_type: String(50) - 'send_message', 'change_status', 'assign', etc
    status: String(20) - 'pending', 'running', 'completed', 'failed', 'cancelled'
    
    # Progress tracking
    total_items: Integer
    processed_items: Integer
    successful_items: Integer
    failed_items: Integer
    skipped_items: Integer
    
    # Details
    parameters: JSON - Job specific params
    results: JSON - Errors, skipped items
    
    # Timestamps
    created_at: DateTime
    started_at: DateTime
    completed_at: DateTime
    
    # Properties
    progress_percent: Calculated (processed/total * 100)
    is_active: Calculated (status in ['pending', 'running'])
```

---

## Frontend Integration Examples

### Saving a Filter
```javascript
const filters = getActiveFilters(); // Your function
const formData = new FormData();
formData.append('filter_name', 'My Leads');
formData.append('filter_desc', 'Important leads');
formData.append('filters', JSON.stringify(filters));
formData.append('is_favorite', true);

fetch('/save-filter', {
    method: 'POST',
    body: formData
})
.then(r => r.json())
.then(data => {
    if (data.success) {
        console.log('Filter saved:', data.id);
        location.reload();
    }
});
```

### Loading a Filter
```javascript
// Just click a button that links to:
window.location.href = `/load-filter/42`;

// Dashboard redirects to / with filters applied
```

### Monitoring a Bulk Job
```javascript
const jobId = 5;
setInterval(() => {
    fetch(`/bulk-job/${jobId}/status`)
        .then(r => r.json())
        .then(data => {
            console.log(`Progress: ${data.progress_percent}%`);
            updateProgressBar(data);
        });
}, 1000); // Check every second
```

### Updating Lead Status (Kanban)
```javascript
const leadId = 123;
const newStatus = 'CONTACTED';

fetch(`/api/lead/${leadId}/status`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: newStatus})
})
.then(r => r.json())
.then(data => {
    if (data.success) {
        console.log('Status updated');
    }
});
```

---

## Error Handling

### Common Status Codes

| Code | Meaning | Response |
|------|---------|----------|
| 200 | Success | JSON with `{"success": true}` |
| 400 | Bad request | JSON with `{"error": "..."}` |
| 403 | Unauthorized | JSON with `{"error": "Unauthorized"}` |
| 404 | Not found | HTML 404 page |
| 500 | Server error | HTML 500 page |

---

## Rate Limiting

Currently no rate limiting on API endpoints. Consider adding:
- 100 requests per minute per IP
- 50 bulk operations per hour per user
- Throttle bulk sends (already has 2s delay)

---

## Future Enhancements

### Planned Endpoints
- `POST /bulk-job` - Create new bulk job programmatically
- `PATCH /bulk-job/<id>` - Modify running job
- `GET /api/jobs` - Get all user's jobs as JSON
- `GET /api/filters` - Get all saved filters as JSON
- `POST /api/filters` - Create filter via API

### Planned Features
- WebSocket for real-time updates
- Export filters as JSON/CSV
- Share filters with other users
- Bulk job scheduling
- Conditional bulk operations

---

## Testing the API

### Using cURL

```bash
# Get lead data
curl http://localhost:5000/api/leads \
  -H "Cookie: session=YOUR_SESSION"

# Save filter
curl -X POST http://localhost:5000/save-filter \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=YOUR_SESSION" \
  -d "filter_name=Test&filters=%7B%7D"

# Get job status
curl http://localhost:5000/bulk-job/1/status \
  -H "Cookie: session=YOUR_SESSION"

# Update lead status
curl -X POST http://localhost:5000/api/lead/1/status \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION" \
  -d '{"status":"CONTACTED"}'
```

### Using Python

```python
import requests
import json

# Assuming you're authenticated
session = requests.Session()
session.headers.update({
    'Cookie': 'session=YOUR_SESSION_ID'
})

# Get leads
response = session.get('http://localhost:5000/api/leads')
leads = response.json()

# Update status
data = {'status': 'CONTACTED'}
response = session.post(
    'http://localhost:5000/api/lead/1/status',
    json=data
)

# Save filter
form_data = {
    'filter_name': 'My Filter',
    'filters': json.dumps({'status': 'HOT'})
}
response = session.post(
    'http://localhost:5000/save-filter',
    data=form_data
)
```

---

## Database Schema Updates

### New Tables
```sql
CREATE TABLE saved_filters (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    filters JSON NOT NULL,
    sort_by VARCHAR(20) DEFAULT 'score',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used DATETIME,
    usage_count INTEGER DEFAULT 0,
    is_favorite BOOLEAN DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE bulk_jobs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    skipped_items INTEGER DEFAULT 0,
    parameters JSON,
    results JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

---

**Last Updated**: January 1, 2026
**API Version**: 1.0
