@echo off
REM ============================================================================
REM  Open-Brain Backend — Fully Automated API Test Suite
REM  Tests all endpoints with a dynamically created session.
REM  Requires: curl, docker (to retrieve OTP from Redis)
REM  Usage:    test_endpoints.bat [BASE_URL]
REM ============================================================================
setlocal enabledelayedexpansion

if "%~1"=="" (set "BASE_URL=http://localhost:8000") else (set "BASE_URL=%~1")

set "PASS=0"
set "FAIL=0"
set "SKIP=0"
set "TOTAL=0"

REM Unique test email/user
for /f %%a in ('powershell -command "[int](Get-Date -UFormat %%s)"') do set "TS=%%a"
set "TEST_EMAIL=auto_test_%TS%@openbrain-test.com"
set "TEST_PASSWORD=TestPass123"

echo ================================================================
echo    Open-Brain Backend - Fully Automated API Test Suite
echo    Target URL: %BASE_URL%
echo    Test Email: %TEST_EMAIL%
echo ================================================================
echo.

REM ----------------------------------------------------------------
REM  SECTION 1: SYSTEM ENDPOINTS
REM ----------------------------------------------------------------
echo [SECTION 1] System Endpoints
echo.

REM 1.1 Health Check
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/health" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Health check OK
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Health check failed
    set /a FAIL+=1
    goto :results
)

REM 1.2 OpenAPI Schema
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/openapi.json" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] OpenAPI schema fetched
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] OpenAPI schema failed
    set /a FAIL+=1
)

REM 1.3 Swagger Docs
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/docs" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Swagger UI OK
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Swagger UI failed
    set /a FAIL+=1
)
echo.

REM ----------------------------------------------------------------
REM  SECTION 2: DYNAMIC REGISTER / LOGIN FLOW (Via Redis OTP)
REM ----------------------------------------------------------------
echo [SECTION 2] Dynamic Registration and Authentication
echo.

REM 2.1 Send Registration OTP
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X POST "%BASE_URL%/auth/register/send-otp" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"%TEST_EMAIL%\",\"password\":\"%TEST_PASSWORD%\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Registration OTP requested
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Send registration OTP failed
    set /a FAIL+=1
    goto :results
)

REM Extract registration_token from Step 1 response
for /f "usebackq tokens=*" %%a in (`powershell -command "(Get-Content '%TEMP%\ob_resp.txt' | Where-Object {$_ -notmatch 'HTTP_'} | ConvertFrom-Json).registration_token"`) do set "REG_TOKEN=%%a"

REM Fetch registration OTP from Redis using the token
for /f "usebackq tokens=*" %%a in (`powershell -command "(docker exec openbrain-redis redis-cli get register:pending:%REG_TOKEN% | ConvertFrom-Json).otp"`) do set "REG_OTP=%%a"
set "REG_OTP=%REG_OTP:~0,6%"
echo   Retrieved Registration OTP: %REG_OTP%

REM 2.2 Complete Registration
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X POST "%BASE_URL%/auth/register" ^
  -H "Content-Type: application/json" ^
  -d "{\"registration_token\":\"%REG_TOKEN%\",\"email\":\"%TEST_EMAIL%\",\"otp\":\"%REG_OTP%\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="201" (
    echo   PASS [201] User registered successfully
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] User registration failed
    set /a FAIL+=1
    goto :results
)

REM 2.3 Login Step 1 (MFA Challenge)
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X POST "%BASE_URL%/auth/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"%TEST_EMAIL%\",\"password\":\"%TEST_PASSWORD%\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Login MFA challenge generated
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Login password verification failed
    set /a FAIL+=1
    goto :results
)

REM Extract mfa_token from response using powershell helper
for /f "usebackq tokens=*" %%a in (`powershell -command "(Get-Content '%TEMP%\ob_resp.txt' | Where-Object {$_ -notmatch 'HTTP_'} | ConvertFrom-Json).mfa_token"`) do set "MFA_TOKEN=%%a"

REM Fetch login OTP from Redis
for /f "usebackq tokens=*" %%i in (`docker exec openbrain-redis redis-cli get otp:login:%TEST_EMAIL%`) do set "LOGIN_OTP=%%i"
set "LOGIN_OTP=%LOGIN_OTP:~0,6%"
echo   Retrieved Login OTP: %LOGIN_OTP%

REM 2.4 Login Step 2 (Verify OTP & Get Tokens)
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X POST "%BASE_URL%/auth/login/verify" ^
  -H "Content-Type: application/json" ^
  -d "{\"mfa_token\":\"%MFA_TOKEN%\",\"otp\":\"%LOGIN_OTP%\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Tokens issued successfully
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Login OTP verification failed
    set /a FAIL+=1
    goto :results
)

REM Extract access_token and refresh_token
for /f "usebackq tokens=*" %%a in (`powershell -command "(Get-Content '%TEMP%\ob_resp.txt' | Where-Object {$_ -notmatch 'HTTP_'} | ConvertFrom-Json).access_token"`) do set "ACCESS_TOKEN=%%a"
for /f "usebackq tokens=*" %%a in (`powershell -command "(Get-Content '%TEMP%\ob_resp.txt' | Where-Object {$_ -notmatch 'HTTP_'} | ConvertFrom-Json).refresh_token"`) do set "REFRESH_TOKEN=%%a"
echo.

REM ----------------------------------------------------------------
REM  SECTION 3: AUTHENTICATED ENDPOINTS
REM ----------------------------------------------------------------
echo [SECTION 3] Authenticated Profile and Chat History
echo.

REM 3.1 Get Profile
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/users/me" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Profile fetched successfully
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Profile fetch failed
    set /a FAIL+=1
)

REM 3.2 Update Profile (PUT /users/me)
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X PUT "%BASE_URL%/users/me" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"test_user_%TS%\",\"first_name\":\"John\",\"last_name\":\"Doe\",\"bio\":\"AI enthusiast\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Profile updated successfully
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Profile update failed
    set /a FAIL+=1
)

REM 3.3 List Chats (Pagination)
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/chats?page=1&page_size=5" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Conversations listed
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Conversations list failed
    set /a FAIL+=1
)

REM 3.4 List Characters
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/ai/characters" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] AI Characters fetched
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] AI Characters failed
    set /a FAIL+=1
)
echo.

REM ----------------------------------------------------------------
REM  SECTION 4: SINGLE SESSION LOGOUT & ACCESS TOKEN BLACKLIST
REM ----------------------------------------------------------------
echo [SECTION 4] Logout and Blacklist Verification
echo.

REM 4.1 Single Session Logout
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" -X POST "%BASE_URL%/auth/logout" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"%REFRESH_TOKEN%\"}" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="200" (
    echo   PASS [200] Logged out current session successfully
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Logout failed
    set /a FAIL+=1
)

REM 4.2 Verify blacklisted access token is blocked
set /a TOTAL+=1
curl -s -w "\nHTTP_CODE:%%{http_code}" "%BASE_URL%/users/me" ^
  -H "Authorization: Bearer %ACCESS_TOKEN%" > "%TEMP%\ob_resp.txt" 2>&1
for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" "%TEMP%\ob_resp.txt"') do set "SC=%%a"
if "%SC%"=="401" (
    echo   PASS [401] Blacklisted token correctly rejected
    set /a PASS+=1
) else (
    echo   FAIL [%SC%] Blacklisted token was not rejected - got %SC%
    set /a FAIL+=1
)
echo.

:results
echo ================================================================
echo    TEST SUMMARY
echo ================================================================
echo    PASSED: %PASS%
echo    FAILED: %FAIL%
echo    TOTAL:  %TOTAL%
echo ================================================================
echo.

if exist "%TEMP%\ob_resp.txt" del "%TEMP%\ob_resp.txt"
endlocal
