# اسکریپت PowerShell برای تولید کلید رمزنگاری

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "تولید کلید رمزنگاری برای ENCRYPTION_KEY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# تولید کلید 32 بایتی و تبدیل به base64
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$key = [Convert]::ToBase64String($bytes)

Write-Host "✅ کلید تولید شد!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 برای استفاده در .env یا environment variable:" -ForegroundColor Yellow
Write-Host "ENCRYPTION_KEY=$key" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  نکات مهم:" -ForegroundColor Red
Write-Host "1. این کلید را در جای امن نگه دارید"
Write-Host "2. هرگز در Git commit نکنید"
Write-Host "3. اگر کلید را گم کنید، داده‌های رمزنگاری شده قابل بازیابی نیستند"
Write-Host "4. در production حتماً از environment variable استفاده کنید"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan






