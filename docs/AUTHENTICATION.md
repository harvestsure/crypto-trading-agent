# Authentication System Documentation

## Overview

CryptoAgent uses a JWT-based authentication system with bcrypt password hashing. The system includes user registration, login, session management, and route protection.

## Architecture

### Frontend (Next.js)
- **Auth Context**: Global authentication state management (`contexts/auth-context.tsx`)
- **Auth API**: API client for authentication endpoints (`lib/auth.ts`)
- **Protected Routes**: Component wrapper for authenticated pages (`components/auth/protected-route.tsx`)
- **Login/Register Pages**: User-facing authentication forms

### Backend (Python/FastAPI)
- **Auth Module**: Core authentication logic (`scripts/backend/auth.py`)
- **Auth Routes**: API endpoints for auth operations (`scripts/backend/routes/auth_routes.py`)
- **Database**: SQLite with users and sessions tables

## Features

### User Registration
- Username validation (min 3 characters)
- Email validation
- Password strength requirements (min 6 characters)
- Password confirmation
- Bcrypt password hashing
- Automatic login after registration

### User Login
- Username/email and password authentication
- JWT token generation (7-day expiration)
- Session creation and management
- Remember me functionality
- Redirect to dashboard after login

### Session Management
- JWT tokens stored in localStorage
- Automatic token verification on mount
- Token refresh on API calls
- Session cleanup on logout
- Multiple device support

### Route Protection
- All dashboard pages require authentication
- Automatic redirect to login for unauthenticated users
- Loading states during authentication checks
- Protected API endpoints on backend

## Usage

### Protecting a Page

\`\`\`typescript
import { ProtectedRoute } from "@/components/auth/protected-route"

export default function MyPage() {
  return (
    <ProtectedRoute>
      <div>Protected content here</div>
    </ProtectedRoute>
  )
}
\`\`\`

### Using Auth Context

\`\`\`typescript
import { useAuth } from "@/contexts/auth-context"

function MyComponent() {
  const { user, isAuthenticated, login, logout } = useAuth()
  
  return (
    <div>
      {isAuthenticated ? (
        <p>Welcome, {user.username}!</p>
      ) : (
        <button onClick={() => login({username, password})}>Login</button>
      )}
    </div>
  )
}
\`\`\`

### Making Authenticated API Calls

The API client automatically includes the JWT token in all requests:

\`\`\`typescript
import { getAgents } from "@/lib/api"

// Token is automatically included
const { data, error } = await getAgents()
\`\`\`

## API Endpoints

### POST /api/auth/register
Register a new user account.

**Request Body:**
\`\`\`json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
\`\`\`

**Response:**
\`\`\`json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "user_abc123",
    "username": "johndoe",
    "email": "john@example.com",
    "full_name": "John Doe"
  }
}
\`\`\`

### POST /api/auth/login
Login with existing credentials.

**Request Body:**
\`\`\`json
{
  "username": "johndoe",
  "password": "securepassword"
}
\`\`\`

**Response:** Same as registration

### POST /api/auth/logout
Logout and invalidate all sessions.

**Headers:**
\`\`\`
Authorization: Bearer <token>
\`\`\`

**Response:**
\`\`\`json
{
  "message": "Successfully logged out"
}
\`\`\`

### GET /api/auth/me
Get current user profile.

**Headers:**
\`\`\`
Authorization: Bearer <token>
\`\`\`

**Response:**
\`\`\`json
{
  "id": "user_abc123",
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "created_at": "2025-01-10T12:00:00",
  "last_login": "2025-01-10T15:30:00"
}
\`\`\`

### GET /api/auth/verify
Verify if token is valid.

**Headers:**
\`\`\`
Authorization: Bearer <token>
\`\`\`

**Response:**
\`\`\`json
{
  "valid": true,
  "user": {
    "id": "user_abc123",
    "username": "johndoe"
  }
}
\`\`\`

## Database Schema

### Users Table
\`\`\`sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
)
\`\`\`

### Sessions Table
\`\`\`sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
\`\`\`

## Security Features

1. **Password Hashing**: Bcrypt with salt (12 rounds)
2. **JWT Tokens**: Signed with HS256 algorithm
3. **Token Expiration**: 7-day expiration for security
4. **HTTP-Only Cookies**: Recommended for production (currently localStorage)
5. **Input Validation**: Pydantic models validate all inputs
6. **SQL Injection Protection**: Parameterized queries
7. **CORS Protection**: Configured in FastAPI
8. **Rate Limiting**: Recommended for production

## Environment Variables

### Backend (Python)
\`\`\`bash
JWT_SECRET_KEY=your-secret-key-here  # Auto-generated if not provided
\`\`\`

### Frontend (Next.js)
\`\`\`bash
NEXT_PUBLIC_API_URL=http://localhost:8000  # Backend API URL
\`\`\`

## Error Handling

The system handles various error scenarios:

- **Invalid Credentials**: 401 Unauthorized
- **Duplicate Username/Email**: 400 Bad Request
- **Expired Token**: 401 Unauthorized, auto-redirect to login
- **Network Errors**: Retry logic with exponential backoff
- **Server Errors**: 500 Internal Server Error with error messages

## Best Practices

1. **Always use HTTPS in production**
2. **Implement rate limiting on auth endpoints**
3. **Use HTTP-only cookies instead of localStorage**
4. **Implement password reset functionality**
5. **Add two-factor authentication**
6. **Log authentication events**
7. **Implement session timeout warnings**
8. **Use strong JWT secret keys**
9. **Rotate JWT secrets periodically**
10. **Implement CSRF protection**

## Testing

### Manual Testing

1. **Registration Flow**:
   - Go to `/register`
   - Fill in username, email, password
   - Submit and verify auto-login
   - Check localStorage for token

2. **Login Flow**:
   - Logout first
   - Go to `/login`
   - Enter credentials
   - Verify redirect to dashboard

3. **Protected Routes**:
   - Logout
   - Try to access `/` or `/agents`
   - Verify redirect to `/login`

4. **Token Expiration**:
   - Login
   - Manually expire token in localStorage
   - Refresh page
   - Verify redirect to login

## Troubleshooting

### Common Issues

**Issue**: "Failed to fetch" error on login
- **Solution**: Ensure backend is running on correct port
- Check NEXT_PUBLIC_API_URL environment variable

**Issue**: Infinite redirect loop
- **Solution**: Clear localStorage and cookies
- Check ProtectedRoute implementation

**Issue**: Token not being sent in requests
- **Solution**: Verify authAPI.getToken() returns valid token
- Check API client token injection logic

**Issue**: CORS errors
- **Solution**: Configure CORS in FastAPI backend
- Allow credentials in fetch requests

## Future Enhancements

- [ ] Password reset via email
- [ ] Two-factor authentication (2FA)
- [ ] OAuth social login (Google, GitHub)
- [ ] Account email verification
- [ ] Password strength meter
- [ ] Session management dashboard
- [ ] Login history and audit logs
- [ ] Account deletion workflow
- [ ] Password change functionality
- [ ] Remember device option
