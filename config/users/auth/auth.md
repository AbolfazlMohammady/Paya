# Login

- URL: `/api/core/login/`
- Method: POST
- Request:

```json
{
"phone":"9339999999"
}
```

- Response:

```json
{
    "detail": "Your code phone +989339999999 --> 7556"
}
```

# Verify

- URL: `/api/core/verify/`
- Method: POST
- Request:

```json
{
"phone":"9339999999",
"code":"5495"
}

```

- Response:

```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MjI2MjQ2MiwiaWF0IjoxNzYyMTc2MDYyLCJqdGkiOiJiZDc4YjA1YjgxNWY0ZGIzYmNjODIwYTQ0OWRmNDg3NiIsInVzZXJfaWQiOiIzIn0.LFZ_IRkim1-cS3vbdYMpuSB1XfbuPHWFHO1vdP83piU",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY0NzY4MDYyLCJpYXQiOjE3NjIxNzYwNjIsImp0aSI6IjIyOGIxYWYwOTc5NTQ3NzI5YWI4NTY3ZmM2MmFmNTRkIiwidXNlcl9pZCI6IjMifQ.8d67aaDjpHMLX2KWwzn9D4O5K_ihvQ8wCmGWZPEkVIc"
}
```

# refresh

- URL: `/api/core/refresh/`

- Method: POST
- Request:

```json
{
    "refresh": ""
}
```

- Response:

```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MjI2MjQ2MiwiaWF0IjoxNzYyMTc2MDYyLCJqdGkiOiJiZDc4YjA1YjgxNWY0ZGIzYmNjODIwYTQ0OWRmNDg3NiIsInVzZXJfaWQiOiIzIn0.LFZ_IRkim1-cS3vbdYMpuSB1XfbuPHWFHO1vdP83piU",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY0NzY4MDYyLCJpYXQiOjE3NjIxNzYwNjIsImp0aSI6IjIyOGIxYWYwOTc5NTQ3NzI5YWI4NTY3ZmM2MmFmNTRkIiwidXNlcl9pZCI6IjMifQ.8d67aaDjpHMLX2KWwzn9D4O5K_ihvQ8wCmGWZPEkVIc"
}
```
