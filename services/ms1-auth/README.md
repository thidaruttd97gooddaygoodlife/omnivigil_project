# MS1 Auth Service

Authentication and authorization service for OmniVigil.

## Responsibilities
- Validate username/password from PostgreSQL
- Issue JWT token for authenticated users
- Verify token and role access for other services

## Endpoints
- `GET /health`
- `POST /auth/login`
- `GET /auth/verify`
- `GET /auth/me`
- `GET /auth/authorize?required_role=technician`

## Default users (seed on startup)
- `security_admin / admin1234` (role: `admin`)
- `technician_a / tech1234` (role: `technician`)
- `viewer_a / view1234` (role: `viewer`)

## Environment
- `POSTGRES_URL` (default: `postgresql://omni:omni_password@localhost:5432/auth`)
- `JWT_SECRET`
- `JWT_ALGORITHM` (default: `HS256`)
- `JWT_EXPIRE_MINUTES` (default: `60`)